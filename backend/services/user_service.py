"""
用户服务
JWT鉴权、用户数据逻辑（处理用户的注册、登录、数据修改等）
"""

import re
from datetime import datetime, timedelta
from flask_jwt_extended import create_access_token, create_refresh_token
from werkzeug.security import generate_password_hash, check_password_hash

from models.user import User, db
from utils.response import error

class UserService:
    """用户服务类"""
    
    @staticmethod
    def validate_email(email):
        """验证邮箱格式"""
        pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
        return re.match(pattern, email) is not None
    
    @staticmethod
    def validate_password(password):
        """验证密码强度"""
        if len(password) < 6:
            return False, '密码长度至少6位'
        
        if not re.search(r'[A-Z]', password):
            return False, '密码必须包含至少一个大写字母'
        
        if not re.search(r'[a-z]', password):
            return False, '密码必须包含至少一个小写字母'
        
        if not re.search(r'\d', password):
            return False, '密码必须包含至少一个数字'
        
        return True, '密码强度合格'
    
    @staticmethod
    def register_user(data):
        """注册用户"""
        try:
            # 验证必要字段
            required_fields = ['username', 'email', 'password']
            for field in required_fields:
                if field not in data:
                    return None, error(f'缺少必要字段: {field}', 400)
            
            # 验证邮箱格式
            if not UserService.validate_email(data['email']):
                return None, error('邮箱格式不正确', 400)
            
            # 验证密码强度
            is_valid, message = UserService.validate_password(data['password'])
            if not is_valid:
                return None, error(f'密码强度不足: {message}', 400)
            
            # 检查用户名是否已存在
            if User.query.filter_by(username=data['username']).first():
                return None, error('用户名已存在', 400)
            
            # 检查邮箱是否已存在
            if User.query.filter_by(email=data['email']).first():
                return None, error('邮箱已注册', 400)
            
            # 创建用户
            user = User(
                username=data['username'],
                email=data['email'],
                password=data['password']
            )
            
            # 设置可选字段
            optional_fields = ['full_name', 'age', 'gender', 'occupation', 'phone',
                             'height', 'weight', 'medical_history', 'current_symptoms']
            
            for field in optional_fields:
                if field in data:
                    setattr(user, field, data[field])
            
            # 设置角色（默认为patient）
            user.role = data.get('role', 'patient')
            
            db.session.add(user)
            db.session.commit()
            
            # 生成访问令牌
            access_token = create_access_token(
                identity=str(user.id),
                expires_delta=timedelta(hours=24)
            )
            
            refresh_token = create_refresh_token(identity=str(user.id))
            
            return {
                'user': user.to_dict(),
                'access_token': access_token,
                'refresh_token': refresh_token
            }, None
            
        except Exception as e:
            db.session.rollback()
            return None, error(f'注册失败: {str(e)}', 500)
    
    @staticmethod
    def login_user(username, password):
        """用户登录"""
        try:
            # 查找用户（支持用户名或邮箱登录）
            user = User.query.filter(
                (User.username == username) | (User.email == username)
            ).first()
            
            if not user:
                return None, error('用户不存在或密码错误', 401)
            
            # 验证密码
            if not user.check_password(password):
                return None, error('用户不存在或密码错误', 401)
            
            # 检查账户状态
            if not user.is_active:
                return None, error('账户已被禁用', 403)
            
            # 生成令牌
            access_token = create_access_token(
                identity=str(user.id),
                expires_delta=timedelta(hours=24)
            )
            
            refresh_token = create_refresh_token(identity=str(user.id))
            
            # 更新最后登录时间
            user.last_login = datetime.utcnow()
            db.session.commit()
            
            return {
                'user': user.to_dict(),
                'access_token': access_token,
                'refresh_token': refresh_token
            }, None
            
        except Exception as e:
            return None, error(f'登录失败: {str(e)}', 500)
    
    @staticmethod
    def get_user_profile(user_id):
        """获取用户资料"""
        try:
            user = User.query.get(user_id)
            
            if not user:
                return None, error('用户不存在', 404)
            
            return user.to_dict(include_sensitive=True), None
            
        except Exception as e:
            return None, error(f'获取资料失败: {str(e)}', 500)
    
    @staticmethod
    def update_user_profile(user_id, data):
        """更新用户资料"""
        try:
            user = User.query.get(user_id)
            
            if not user:
                return None, error('用户不存在', 404)
            
            # 定义允许更新的字段
            allowed_fields = [
                'full_name', 'age', 'gender', 'occupation', 'phone',
                'height', 'weight', 'medical_history', 'current_symptoms'
            ]
            
            # 更新字段
            updated = False
            for field in allowed_fields:
                if field in data:
                    setattr(user, field, data[field])
                    updated = True
            
            if updated:
                user.updated_at = datetime.utcnow()
                db.session.commit()
            
            return user.to_dict(include_sensitive=True), None
            
        except Exception as e:
            db.session.rollback()
            return None, error(f'更新资料失败: {str(e)}', 500)
    
    @staticmethod
    def change_password(user_id, old_password, new_password):
        """修改密码"""
        try:
            user = User.query.get(user_id)
            
            if not user:
                return None, error('用户不存在', 404)
            
            # 验证旧密码
            if not user.check_password(old_password):
                return None, error('旧密码错误', 401)
            
            # 验证新密码强度
            is_valid, message = UserService.validate_password(new_password)
            if not is_valid:
                return None, error(f'新密码强度不足: {message}', 400)
            
            # 设置新密码
            user.set_password(new_password)
            user.updated_at = datetime.utcnow()
            db.session.commit()
            
            return {'message': '密码修改成功'}, None
            
        except Exception as e:
            db.session.rollback()
            return None, error(f'修改密码失败: {str(e)}', 500)
    
    @staticmethod
    def get_users_by_role(role=None, page=1, per_page=20):
        """根据角色获取用户列表"""
        try:
            query = User.query
            
            if role:
                query = query.filter_by(role=role)
            
            # 分页
            pagination = query.paginate(page=page, per_page=per_page, error_out=False)
            
            users = [user.to_dict() for user in pagination.items]
            
            return {
                'users': users,
                'total': pagination.total,
                'page': pagination.page,
                'per_page': pagination.per_page,
                'pages': pagination.pages
            }, None
            
        except Exception as e:
            return None, error(f'获取用户列表失败: {str(e)}', 500)
    
    @staticmethod
    def get_user_statistics():
        """获取用户统计信息"""
        try:
            # 统计各类用户数量
            total_users = User.query.count()
            patients = User.query.filter_by(role='patient').count()
            doctors = User.query.filter_by(role='doctor').count()
            admins = User.query.filter_by(role='admin').count()
            
            # 统计活跃用户
            active_users = User.query.filter_by(is_active=True).count()
            
            # 统计最近注册的用户（最近7天）
            week_ago = datetime.utcnow() - timedelta(days=7)
            recent_users = User.query.filter(User.created_at >= week_ago).count()
            
            # 统计已验证邮箱的用户
            verified_users = User.query.filter_by(is_verified=True).count()
            
            return {
                'total_users': total_users,
                'patients': patients,
                'doctors': doctors,
                'admins': admins,
                'active_users': active_users,
                'recent_users': recent_users,
                'verified_users': verified_users
            }, None
            
        except Exception as e:
            return None, error(f'获取统计信息失败: {str(e)}', 500)
    
    @staticmethod
    def update_user_status(user_id, is_active=None, is_verified=None):
        """更新用户状态（仅管理员）"""
        try:
            user = User.query.get(user_id)
            
            if not user:
                return None, error('用户不存在', 404)
            
            updated = False
            
            if is_active is not None:
                user.is_active = is_active
                updated = True
            
            if is_verified is not None:
                user.is_verified = is_verified
                updated = True
            
            if updated:
                user.updated_at = datetime.utcnow()
                db.session.commit()
            
            return user.to_dict(), None
            
        except Exception as e:
            db.session.rollback()
            return None, error(f'更新用户状态失败: {str(e)}', 500)
