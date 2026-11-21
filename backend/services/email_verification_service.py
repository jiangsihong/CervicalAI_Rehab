"""Email ownership verification. Codes are never returned or logged."""
import hashlib
import hmac
import secrets
import smtplib
import ssl
from datetime import datetime, timedelta
from email.message import EmailMessage
from uuid import uuid4

from flask import current_app
from sqlalchemy.exc import IntegrityError

from models.user import db
from models.email_verification import AuthRateLimit, EmailVerification


class AuthError(ValueError):
    def __init__(self, message, status=400):
        super().__init__(message)
        self.status = status


def rate_limit(scope, identity, limit, seconds):
    """Atomic database counters shared across threads, processes and restarts."""
    now = datetime.utcnow()
    key = hashlib.sha256((scope + ':' + identity).encode('utf-8')).hexdigest()
    row = AuthRateLimit.query.get(key)
    if row is None:
        try:
            with db.session.begin_nested():
                db.session.add(AuthRateLimit(key=key, count=0, reset_at=now))
                db.session.flush()
        except IntegrityError:
            pass  # Another worker created this counter first.
    updated = AuthRateLimit.query.filter_by(key=key).filter(AuthRateLimit.reset_at <= now).update(
        {'count': 1, 'reset_at': now + timedelta(seconds=seconds)}, synchronize_session=False)
    if not updated:
        updated = AuthRateLimit.query.filter_by(key=key).filter(
            AuthRateLimit.count < limit, AuthRateLimit.reset_at > now).update(
                {'count': AuthRateLimit.count + 1}, synchronize_session=False)
    db.session.commit()
    if not updated:
        raise AuthError('操作过于频繁，请稍后再试', 429)


def code_digest(challenge_id, code):
    secret = current_app.config['SECRET_KEY']
    return hmac.new(secret.encode('utf-8'), (challenge_id + ':' + code).encode('utf-8'),
                    hashlib.sha256).hexdigest()


def send_email_code(email, code, purpose):
    config = current_app.config
    if not all(config.get(key) for key in ('MAIL_HOST', 'MAIL_USERNAME', 'MAIL_PASSWORD', 'MAIL_FROM')):
        raise AuthError('验证码邮件服务尚未配置，请联系服务提供方', 503)
    message = EmailMessage()
    message['Subject'] = 'CervicalAI 患者自测 - {}验证码'.format('注册' if purpose == 'register' else '登录')
    message['From'] = config['MAIL_FROM']
    message['To'] = email
    message.set_content('您的验证码是：{}\n\n5 分钟内有效，仅限本次{}使用。请勿向他人透露。'
                        '\n如果不是您本人操作，请忽略此邮件。'.format(
                            code, '注册' if purpose == 'register' else '登录'))
    context = ssl.create_default_context()
    try:
        if config['MAIL_SECURITY'] == 'ssl':
            connection = smtplib.SMTP_SSL(config['MAIL_HOST'], config['MAIL_PORT'], timeout=15, context=context)
        elif config['MAIL_SECURITY'] == 'starttls':
            connection = smtplib.SMTP(config['MAIL_HOST'], config['MAIL_PORT'], timeout=15)
        else:
            raise AuthError('验证码邮件服务的加密配置无效', 503)
        with connection as smtp:
            if config['MAIL_SECURITY'] == 'starttls':
                smtp.starttls(context=context)
            smtp.login(config['MAIL_USERNAME'], config['MAIL_PASSWORD'])
            if smtp.send_message(message):
                raise AuthError('邮件发送失败，请稍后重试', 503)
    except (smtplib.SMTPException, OSError):
        # Do not expose credentials, message contents, or provider responses.
        current_app.logger.warning('Verification email transport failed')
        raise AuthError('邮件发送失败，请稍后重试或联系服务提供方', 503)


def issue_code(email, purpose, subject, remote_addr):
    rate_limit('mail-ip', remote_addr, 20, 3600)
    rate_limit('mail-hour', email, 5, 3600)
    rate_limit('mail-cooldown', email, 1, 60)
    now = datetime.utcnow()
    # Bounded retention; valid challenges and active limits are preserved.
    EmailVerification.query.filter(EmailVerification.expires_at < now - timedelta(days=1)).delete()
    AuthRateLimit.query.filter(AuthRateLimit.reset_at < now - timedelta(days=1)).delete()
    challenge_id = uuid4().hex
    code = '{:06d}'.format(secrets.randbelow(1000000))
    challenge = EmailVerification(id=challenge_id, email=email, purpose=purpose, subject=subject,
                                  code_hash=code_digest(challenge_id, code),
                                  expires_at=now + timedelta(minutes=5))
    db.session.add(challenge)
    db.session.commit()
    # Pending challenges cannot be redeemed while the SMTP call is in progress.
    send_email_code(email, code, purpose)
    EmailVerification.query.filter_by(email=email, purpose=purpose, consumed=False).filter(
        EmailVerification.id != challenge_id).update({'consumed': True}, synchronize_session=False)
    challenge.delivered = True
    db.session.commit()
    local, domain = email.rsplit('@', 1)
    return {'verification_id': challenge_id, 'expires_in': 300, 'retry_after': 60,
            'email_hint': local[:1] + '***@' + domain}


def consume_code(data, email, purpose, subject):
    challenge_id = data.get('verification_id')
    code = data.get('verification_code')
    if not isinstance(challenge_id, str) or len(challenge_id) != 32:
        raise AuthError('请先获取邮箱验证码')
    if not isinstance(code, str) or len(code) != 6 or not code.isascii() or not code.isdigit():
        raise AuthError('请输入 6 位数字邮箱验证码')
    # Reserve an attempt atomically before comparing; all failure paths count.
    query = EmailVerification.query.filter_by(id=challenge_id, email=email, purpose=purpose,
                                              subject=subject, delivered=True, consumed=False).filter(
        EmailVerification.expires_at > datetime.utcnow(), EmailVerification.attempts < 5)
    if not query.update({'attempts': EmailVerification.attempts + 1}, synchronize_session=False):
        db.session.commit()
        raise AuthError('验证码已过期、失效或错误次数过多，请重新获取')
    db.session.commit()
    challenge = db.session.query(EmailVerification).populate_existing().get(challenge_id)
    if not hmac.compare_digest(challenge.code_hash, code_digest(challenge_id, code)):
        raise AuthError('验证码不正确，请检查邮件后重试')
    # Exactly one request can redeem the challenge, even with concurrent workers.
    claimed = EmailVerification.query.filter_by(id=challenge_id, consumed=False, delivered=True).filter(
        EmailVerification.expires_at > datetime.utcnow()).update({'consumed': True}, synchronize_session=False)
    if not claimed:
        db.session.commit()
        raise AuthError('验证码已使用，请重新获取')
    # Caller commits the claim together with account creation / verification.
