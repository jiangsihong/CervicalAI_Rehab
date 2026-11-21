import unittest
from datetime import datetime, timedelta
from unittest.mock import patch

from flask_jwt_extended import create_access_token

from app import create_app
from models.user import User, db
from models.email_verification import EmailVerification, AuthRateLimit
from services.email_verification_service import AuthError, send_email_code


class EmailLoginTests(unittest.TestCase):
    def setUp(self):
        self.app = create_app('testing')
        self.context = self.app.app_context()
        self.context.push()
        self.client = self.app.test_client()
        self.mail = patch('services.email_verification_service.send_email_code').start()
        self.registration = {'username': 'patient_test', 'email': 'patient@example.com', 'password': 'Secure123'}
        self.user = User(username='existing', email='existing@example.com', password='old123')
        db.session.add(self.user)
        db.session.commit()
        self.credentials = {'username': self.user.username, 'password': 'old123'}

    def tearDown(self):
        patch.stopall()
        db.session.remove()
        db.drop_all()
        self.context.pop()

    def post(self, path, payload):
        return self.client.post('/api/user/' + path, json=payload)

    def code(self, purpose='login', payload=None):
        payload = dict(payload or (self.credentials if purpose == 'login' else self.registration))
        response = self.post('email-code', dict(payload, purpose=purpose))
        self.assertEqual(response.status_code, 200, response.get_json())
        code = self.mail.call_args[0][1]
        data = response.get_json()['data']
        self.assertNotIn('verification_code', data)
        self.assertNotIn('code', data)
        payload.update(verification_id=data['verification_id'], verification_code=code)
        self.assertNotEqual(EmailVerification.query.get(data['verification_id']).code_hash, code)
        return payload

    def headers(self):
        return {'Authorization': 'Bearer ' + create_access_token(identity=str(self.user.id))}

    def test_registration_requires_email_and_fixes_patient_role(self):
        self.assertEqual(self.post('register', self.registration).status_code, 400)
        payload = self.code('register')
        payload.update(role='admin', is_verified=False)
        result = self.post('register', payload)
        self.assertEqual(result.status_code, 201, result.get_json())
        user = result.get_json()['data']['user']
        self.assertEqual(user['role'], 'patient')
        self.assertTrue(user['is_verified'])
        self.assertFalse(user['profile_complete'])
        self.assertEqual(len(user['profile_missing_fields']), 3)

    def test_existing_login_requires_password_and_single_use_code(self):
        self.assertEqual(self.post('login', self.credentials).status_code, 400)
        payload = self.code()
        response = self.post('login', payload)
        self.assertEqual(response.status_code, 200, response.get_json())
        self.assertTrue(response.get_json()['data']['user']['is_verified'])
        self.assertIn('access_token', response.get_json()['data'])
        self.assertEqual(self.post('login', payload).status_code, 400)

    def test_login_by_email_case_insensitive_and_mails_bound_address(self):
        payload = self.code(payload={'username': 'EXISTING@EXAMPLE.COM', 'password': 'old123', 'email': 'attacker@example.com'})
        self.assertEqual(self.mail.call_args[0][0], 'existing@example.com')
        self.assertEqual(self.post('login', payload).status_code, 200)

    def test_wrong_password_disabled_and_nonpatient_never_send_mail(self):
        self.assertEqual(self.post('email-code', dict(self.credentials, password='bad', purpose='login')).status_code, 401)
        self.user.is_active = False
        db.session.commit()
        self.assertEqual(self.post('email-code', dict(self.credentials, purpose='login')).status_code, 403)
        self.user.is_active = True
        self.user.role = 'admin'
        db.session.commit()
        self.assertEqual(self.post('email-code', dict(self.credentials, purpose='login')).status_code, 403)
        self.mail.assert_not_called()

    def test_wrong_code_locks_after_five_attempts(self):
        payload = self.code()
        wrong = '000000' if payload['verification_code'] != '000000' else '111111'
        for _ in range(5):
            self.assertEqual(self.post('login', dict(payload, verification_code=wrong)).status_code, 400)
        self.assertEqual(self.post('login', payload).status_code, 400)
        self.assertEqual(EmailVerification.query.get(payload['verification_id']).attempts, 5)

    def test_expired_and_pending_codes_rejected(self):
        payload = self.code()
        row = EmailVerification.query.get(payload['verification_id'])
        row.delivered = False
        db.session.commit()
        self.assertEqual(self.post('login', payload).status_code, 400)
        row.delivered = True
        row.expires_at = datetime.utcnow() - timedelta(seconds=1)
        db.session.commit()
        self.assertEqual(self.post('login', payload).status_code, 400)

    def test_challenge_cannot_cross_account_or_purpose(self):
        payload = self.code()
        other = User(username='other', email='other@example.com', password='Other123')
        db.session.add(other)
        db.session.commit()
        self.assertEqual(self.post('login', dict(payload, username='other', password='Other123')).status_code, 400)
        self.assertEqual(self.post('register', dict(self.registration, verification_id=payload['verification_id'],
                                                  verification_code=payload['verification_code'])).status_code, 400)
        self.assertEqual(self.post('login', payload).status_code, 200)

    def test_resend_cooldown_persists_and_successful_resend_invalidates_old_code(self):
        old = self.code()
        db.session.remove()
        self.assertEqual(self.post('email-code', dict(self.credentials, purpose='login')).status_code, 429)
        self.assertEqual(self.mail.call_count, 1)
        AuthRateLimit.query.update({'reset_at': datetime.utcnow() - timedelta(seconds=1)})
        db.session.commit()
        new = self.code()
        self.assertEqual(self.post('login', old).status_code, 400)
        self.assertEqual(self.post('login', new).status_code, 200)

    def test_password_bruteforce_limit(self):
        for _ in range(15):
            self.assertEqual(self.post('login', dict(self.credentials, password='bad')).status_code, 401)
        self.assertEqual(self.post('login', dict(self.credentials, password='bad')).status_code, 429)

    def test_email_and_username_share_password_attempt_budget(self):
        for index in range(15):
            identifier = 'existing' if index % 2 else 'EXISTING@EXAMPLE.COM'
            self.assertEqual(self.post('login', {'username': identifier, 'password': 'bad'}).status_code, 401)
        self.assertEqual(self.post('email-code', dict(self.credentials, purpose='login')).status_code, 429)
        self.mail.assert_not_called()

    def test_mail_hourly_limit_survives_cooldown_expiry(self):
        for _ in range(5):
            self.code()
            AuthRateLimit.query.filter(AuthRateLimit.reset_at < datetime.utcnow() + timedelta(minutes=2)).update(
                {'reset_at': datetime.utcnow() - timedelta(seconds=1)})
            db.session.commit()
        self.assertEqual(self.post('email-code', dict(self.credentials, purpose='login')).status_code, 429)
        self.assertEqual(self.mail.call_count, 5)

    def test_failed_resend_preserves_previous_delivered_code(self):
        old = self.code()
        AuthRateLimit.query.filter(AuthRateLimit.reset_at < datetime.utcnow() + timedelta(minutes=2)).update(
            {'reset_at': datetime.utcnow() - timedelta(seconds=1)})
        db.session.commit()
        self.mail.side_effect = AuthError('邮件发送失败', 503)
        self.assertEqual(self.post('email-code', dict(self.credentials, purpose='login')).status_code, 503)
        self.assertEqual(self.post('login', old).status_code, 200)

    def test_invalid_inputs_and_weak_registration_password(self):
        for payload in [None, [], 'text', 42, {}, {'username': [], 'password': 'abc'}]:
            self.assertEqual(self.post('login', payload).status_code, 400)
        for fields in [{'email': 'bad'}, {'email': 'x..y@example.com'}, {'username': 'a'},
                       {'username': '<script>'}, {'password': '12345678'}, {'password': 'abcdefgh'},
                       {'password': ['password']}, {'age': True}]:
            self.assertEqual(self.post('register', dict(self.registration, **fields)).status_code, 400)

    def test_optional_profile_completion_validation_and_atomic_rejection(self):
        headers = self.headers()
        for payload in [{'age': -1}, {'age': 121}, {'age': 1.5}, {'age': True}, {'height': 0},
                        {'weight': 500}, {'gender': 'invalid'}, {'full_name': 'x' * 51},
                        {'phone': 'abc'}, {'medical_history': 'x' * 2001}, [], None]:
            result = self.client.put('/api/user/profile', json=payload, headers=headers)
            self.assertEqual(result.status_code, 400, result.get_json())
        result = self.client.put('/api/user/profile', json={'full_name': '小明', 'age': 0, 'gender': 'other',
                                                           'height': 170.5, 'role': 'admin'}, headers=headers)
        self.assertEqual(result.status_code, 200)
        user = result.get_json()['data']['user']
        self.assertTrue(user['profile_complete'])
        self.assertEqual(user['profile_missing_fields'], [])
        self.assertEqual(user['role'], 'patient')
        self.assertIsNone(user['phone'])
        self.assertEqual(self.client.put('/api/user/profile', json={'age': 23, 'phone': 'bad'}, headers=headers).status_code, 400)
        self.assertEqual(self.user.age, 0)

    def test_password_change_uses_new_rules_but_old_login_still_works(self):
        headers = self.headers()
        self.assertEqual(self.client.post('/api/user/change-password', json={'old_password': 'old123', 'new_password': '12345678'}, headers=headers).status_code, 400)
        self.assertEqual(self.client.post('/api/user/change-password', json={'old_password': 'old123', 'new_password': 'NewSecure123'}, headers=headers).status_code, 200)
        self.assertTrue(self.user.check_password('NewSecure123'))

    def test_mail_failure_never_delivers_or_bypasses_code(self):
        self.mail.side_effect = AuthError('邮件发送失败', 503)
        response = self.post('email-code', dict(self.credentials, purpose='login'))
        self.assertEqual(response.status_code, 503)
        row = EmailVerification.query.first()
        self.assertFalse(row.delivered)
        code = self.mail.call_args[0][1]
        self.assertEqual(self.post('login', dict(self.credentials, verification_id=row.id, verification_code=code)).status_code, 400)

    def test_unconfigured_real_sender_fails_closed(self):
        self.app.config.update(MAIL_HOST='', MAIL_USERNAME='', MAIL_PASSWORD='', MAIL_FROM='')
        with self.assertRaises(AuthError) as result:
            send_email_code('patient@example.com', '123456', 'login')
        self.assertEqual(result.exception.status, 503)

    def test_tls_sender_uses_configured_sender_and_arbitrary_recipient(self):
        self.app.config.update(MAIL_HOST='smtp.example.com', MAIL_PORT=465, MAIL_SECURITY='ssl',
                               MAIL_USERNAME='sender@example.com', MAIL_PASSWORD='local-test-only', MAIL_FROM='sender@example.com')
        with patch('services.email_verification_service.smtplib.SMTP_SSL') as smtp:
            smtp.return_value.__enter__.return_value.send_message.return_value = {}
            send_email_code('patient@qq.com', '123456', 'register')
            connection = smtp.return_value.__enter__.return_value
            connection.login.assert_called_once_with('sender@example.com', 'local-test-only')
            message = connection.send_message.call_args[0][0]
            self.assertEqual(message['To'], 'patient@qq.com')
            self.assertEqual(message['From'], 'sender@example.com')
            self.assertIn('123456', message.get_content())
        self.app.config.update(MAIL_PORT=587, MAIL_SECURITY='starttls')
        with patch('services.email_verification_service.smtplib.SMTP') as smtp:
            smtp.return_value.__enter__.return_value.send_message.return_value = {}
            send_email_code('patient@163.com', '123456', 'login')
            connection = smtp.return_value.__enter__.return_value
            self.assertTrue(connection.starttls.called)
            self.assertEqual(connection.send_message.call_args[0][0]['To'], 'patient@163.com')


if __name__ == '__main__':
    unittest.main()
