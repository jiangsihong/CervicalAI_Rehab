"""
用户API路由
用户注册/登录/信息修改
"""

from flask import Blueprint, request, jsonify, current_app
from sqlalchemy import func
from sqlalchemy.exc import IntegrityError
from services.email_verification_service import AuthError, issue_code, consume_code, rate_limit
from utils.user_validation import json_object, text, password_value, registration_data, profile_data
from flask_jwt_extended import create_access_token, jwt_required, get_jwt_identity
from datetime import timedelta

from models.user import db, User
from utils.response import success, error

# 创建蓝图
user_bp = Blueprint('user', __name__, url_prefix='/api/user')

def request_data():
    return json_object(request.get_json(silent=True))


def login_user(data):
    identifier = text(data, 'username', '用户名或邮箱', 100)
    password = password_value(data)
    ip = request.remote_addr or 'unknown'
    rate_limit('password-ip', ip, 60, 900)
    if '@' in identifier:
        user = User.query.filter(func.lower(User.email) == identifier.lower()).first()
    else:
        user = User.query.filter_by(username=identifier).first()
    rate_limit('password-account', 'user:' + str(user.id) if user else 'unknown:' + identifier.lower(), 15, 900)
    if not user or not user.check_password(password):
        raise AuthError('账号或密码不正确', 401)
    if not user.is_active:
        raise AuthError('账户已被禁用', 403)
    if user.role != 'patient':
        raise AuthError('此入口仅用于患者自测账号', 403)
    return user


def account_result(user, message, code=200):
    token = create_access_token(identity=str(user.id), expires_delta=timedelta(hours=24))
    return success({'message': message, 'user': user.to_dict(include_sensitive=True),
                    'access_token': token}, code=code)


@user_bp.errorhandler(AuthError)
def auth_error(exc):
    db.session.rollback()
    return error(str(exc), exc.status)


@user_bp.route('/email-code', methods=['POST'])
def send_verification_code():
    data = request_data()
    purpose = data.get('purpose')
    if purpose == 'login':
        user = login_user(data)
        email, subject = user.email.lower(), str(user.id)
    elif purpose == 'register':
        rate_limit('register-ip', request.remote_addr or 'unknown', 30, 3600)
        username, email, password = registration_data(data)
        if User.query.filter_by(username=username).first() or User.query.filter(func.lower(User.email) == email).first():
            raise AuthError('用户名或邮箱已被使用，请登录或更换后重试')
        subject = username
    else:
        raise AuthError('请选择有效的验证码用途')
    result = issue_code(email, purpose, subject, request.remote_addr or 'unknown')
    return success(result, message='验证码已发送，请查看邮箱（含垃圾邮件）')


@user_bp.route('/register', methods=['POST'])
def register():
    data = request_data()
    rate_limit('register-submit-ip', request.remote_addr or 'unknown', 30, 3600)
    username, email, password = registration_data(data)
    profile = profile_data(data)
    if User.query.filter_by(username=username).first() or User.query.filter(func.lower(User.email) == email).first():
        raise AuthError('用户名或邮箱已被使用，请登录或更换后重试')
    consume_code(data, email, 'register', username)
    try:
        user = User(username=username, email=email, password=password, role='patient', is_verified=True)
        user.update_profile(profile)
        db.session.add(user)
        db.session.commit()
    except IntegrityError:
        db.session.rollback()
        raise AuthError('用户名或邮箱已被使用，请更换后重试')
    return account_result(user, '注册成功', 201)


@user_bp.route('/login', methods=['POST'])
def login():
    data = request_data()
    user = login_user(data)
    consume_code(data, user.email.lower(), 'login', str(user.id))
    user.is_verified = True
    db.session.commit()
    return account_result(user, '登录成功')

@user_bp.route('/profile', methods=['GET'])
@jwt_required()
def get_profile():
    """获取用户资料"""
    try:
        user_id = get_jwt_identity()
        user = User.query.get(user_id)
        
        if not user:
            return error('用户不存在', 404)
        
        return success({
            'user': user.to_dict(include_sensitive=True)
        })
        
    except Exception as e:
        return error(f'获取资料失败: {str(e)}', 500)

@user_bp.route('/profile', methods=['PUT'])
@jwt_required()
def update_profile():
    """更新用户资料"""
    try:
        user_id = get_jwt_identity()
        user = User.query.get(user_id)
        
        if not user:
            return error('用户不存在', 404)
        
        data = request_data()
        validated = profile_data(data)
        user.update_profile(validated)
        db.session.commit()
        
        return success({
            'message': '资料更新成功',
            'user': user.to_dict(include_sensitive=True)
        })
        
    except AuthError:
        raise
    except Exception:
        db.session.rollback()
        current_app.logger.exception('Profile update failed')
        return error('资料保存失败，请稍后重试', 500)

@user_bp.route('/change-password', methods=['POST'])
@jwt_required()
def change_password():
    """修改密码"""
    try:
        user_id = get_jwt_identity()
        user = User.query.get(user_id)
        
        if not user:
            return error('用户不存在', 404)
        
        data = request_data()
        password_value(data, 'old_password')
        password_value(data, 'new_password', new=True)
        rate_limit('change-password', str(user.id), 10, 900)
        
        # 验证旧密码
        if not user.check_password(data['old_password']):
            return error('旧密码错误', 401)
        
        # 设置新密码
        user.set_password(data['new_password'])
        db.session.commit()
        
        return success({
            'message': '密码修改成功'
        })
        
    except AuthError:
        raise
    except Exception:
        db.session.rollback()
        current_app.logger.exception('Password update failed')
        return error('密码修改失败，请稍后重试', 500)

@user_bp.route('/list', methods=['GET'])
@jwt_required()
def list_users():
    """获取用户列表（仅管理员）"""
    try:
        user_id = get_jwt_identity()
        current_user = User.query.get(user_id)
        
        # 检查权限
        if current_user.role != 'admin':
            return error('权限不足', 403)
        
        # 获取查询参数
        role = request.args.get('role')
        page = int(request.args.get('page', 1))
        per_page = int(request.args.get('per_page', 20))
        
        # 构建查询
        query = User.query
        
        if role:
            query = query.filter_by(role=role)
        
        # 分页
        pagination = query.paginate(page=page, per_page=per_page, error_out=False)
        
        users = [user.to_dict() for user in pagination.items]
        
        return success({
            'users': users,
            'total': pagination.total,
            'page': pagination.page,
            'per_page': pagination.per_page,
            'pages': pagination.pages
        })
        
    except Exception as e:
        return error(f'获取用户列表失败: {str(e)}', 500)

@user_bp.route('/<int:user_id>', methods=['GET'])
@jwt_required()
def get_user_by_id(user_id):
    """根据ID获取用户信息（仅管理员）"""
    try:
        current_user_id = get_jwt_identity()
        current_user = User.query.get(current_user_id)
        
        # 检查权限
        if current_user.role != 'admin' and str(current_user_id) != str(user_id):
            return error('权限不足', 403)
        
        user = User.query.get(user_id)
        
        if not user:
            return error('用户不存在', 404)
        
        include_sensitive = (current_user.role == 'admin')
        
        return success({
            'user': user.to_dict(include_sensitive=include_sensitive)
        })
        
    except Exception as e:
        return error(f'获取用户信息失败: {str(e)}', 500)

@user_bp.route('/stats', methods=['GET'])
@jwt_required()
def user_stats():
    """用户统计信息（仅管理员）"""
    try:
        user_id = get_jwt_identity()
        current_user = User.query.get(user_id)
        
        # 检查权限
        if current_user.role != 'admin':
            return error('权限不足', 403)
        
        # 统计各类用户数量
        total_users = User.query.count()
        patients = User.query.filter_by(role='patient').count()
        doctors = User.query.filter_by(role='doctor').count()
        admins = User.query.filter_by(role='admin').count()
        
        # 统计活跃用户
        active_users = User.query.filter_by(is_active=True).count()
        
        # 统计最近注册的用户
        from datetime import datetime, timedelta
        week_ago = datetime.utcnow() - timedelta(days=7)
        recent_users = User.query.filter(User.created_at >= week_ago).count()
        
        return success({
            'total_users': total_users,
            'patients': patients,
            'doctors': doctors,
            'admins': admins,
            'active_users': active_users,
            'recent_users': recent_users
        })
        
    except Exception as e:
        return error(f'获取统计信息失败: {str(e)}', 500)
