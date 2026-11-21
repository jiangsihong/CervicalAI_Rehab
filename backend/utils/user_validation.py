"""Server-side account and optional patient profile validation."""
import math
import re

from services.email_verification_service import AuthError


def json_object(data):
    if not isinstance(data, dict):
        raise AuthError('请提交有效的表单数据')
    return data


def text(data, field, label, maximum, minimum=1):
    value = data.get(field)
    if not isinstance(value, str):
        raise AuthError('请填写' + label)
    value = value.strip()
    if not minimum <= len(value) <= maximum or any(ord(char) < 32 for char in value):
        raise AuthError('{}长度应为 {}–{} 个字符，且不能包含控制字符'.format(label, minimum, maximum))
    return value


def email_address(data):
    email = text(data, 'email', '邮箱', 100).lower()
    # Accept common providers without a provider allowlist; ownership is checked by email.
    if not re.fullmatch(r"[A-Za-z0-9!#$%&'*+/=?^_`{|}~.-]+@[A-Za-z0-9](?:[A-Za-z0-9.-]*[A-Za-z0-9])?\.[A-Za-z]{2,63}", email):
        raise AuthError('请输入有效的邮箱地址')
    local, domain = email.rsplit('@', 1)
    if len(local) > 64 or local.startswith('.') or local.endswith('.') or '..' in email or any(
            not part or len(part) > 63 or part.startswith('-') or part.endswith('-') for part in domain.split('.')):
        raise AuthError('请输入有效的邮箱地址')
    return email


def password_value(data, field='password', new=False):
    password = data.get(field)
    if not isinstance(password, str) or not 1 <= len(password) <= 128:
        raise AuthError('密码不能为空，且不能超过 128 位')
    if new and (len(password) < 8 or not re.search(r'[A-Za-z]', password) or not re.search(r'[0-9]', password)
                or any(ord(char) < 32 or ord(char) == 127 for char in password)):
        raise AuthError('新密码需为 8–128 位，并包含英文字母和数字')
    return password


def registration_data(data):
    username = text(data, 'username', '用户名', 50, 2)
    if not re.fullmatch(r'[A-Za-z0-9_\u4e00-\u9fff.-]+', username):
        raise AuthError('用户名仅支持中文、英文字母、数字、下划线、点和短横线')
    return username, email_address(data), password_value(data, new=True)


def profile_data(data):
    result = {}
    limits = {'full_name': 50, 'occupation': 100, 'phone': 20,
              'medical_history': 2000, 'current_symptoms': 2000}
    for field, limit in limits.items():
        if field not in data:
            continue
        value = data[field]
        if value is None or value == '':
            result[field] = None
            continue
        multiline = field in ('medical_history', 'current_symptoms')
        if not isinstance(value, str) or len(value.strip()) > limit or any(
                ord(c) == 127 or (ord(c) < 32 and (not multiline or c not in '\r\n\t')) for c in value):
            raise AuthError('资料格式不正确或内容过长：' + field)
        result[field] = value.strip() or None
    if result.get('phone') and (not re.fullmatch(r'\+?[0-9 ()-]{6,20}', result['phone']) or
                                len(re.findall(r'[0-9]', result['phone'])) < 6):
        raise AuthError('联系电话需为 6–20 位，可包含数字、区号和短横线')
    if 'gender' in data:
        if data['gender'] not in (None, '', 'male', 'female', 'other'):
            raise AuthError('请选择有效的性别选项')
        result['gender'] = data['gender'] or None
    for field, low, high in [('age', 0, 120), ('height', 30, 250), ('weight', 1, 300)]:
        if field not in data:
            continue
        value = data[field]
        if value is None or value == '':
            result[field] = None
            continue
        if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or not low <= value <= high:
            raise AuthError('{}应在 {}–{} 范围内'.format({'age': '年龄', 'height': '身高', 'weight': '体重'}[field], low, high))
        if field == 'age' and int(value) != value:
            raise AuthError('年龄需为整数')
        result[field] = int(value) if field == 'age' else float(value)
    return result
