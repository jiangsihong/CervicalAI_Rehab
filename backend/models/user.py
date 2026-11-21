"""
用户模型
定义用户表结构，包含用户基本信息
"""

from datetime import datetime
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash

db = SQLAlchemy()

class User(db.Model):
    """用户表模型"""
    __tablename__ = 'users'
    
    # 基本信息
    id = db.Column(db.Integer, primary_key=True, autoincrement=True, comment='用户ID')
    username = db.Column(db.String(50), unique=True, nullable=False, comment='用户名')
    email = db.Column(db.String(100), unique=True, nullable=False, comment='邮箱')
    password_hash = db.Column(db.String(255), nullable=False, comment='密码哈希')
    
    # 个人信息
    full_name = db.Column(db.String(100), nullable=True, comment='全名')
    age = db.Column(db.Integer, nullable=True, comment='年龄')
    gender = db.Column(db.Enum('male', 'female', 'other'), nullable=True, comment='性别')
    occupation = db.Column(db.String(100), nullable=True, comment='职业')
    phone = db.Column(db.String(20), nullable=True, comment='手机号')
    
    # 医疗信息
    height = db.Column(db.Float, nullable=True, comment='身高(cm)')
    weight = db.Column(db.Float, nullable=True, comment='体重(kg)')
    medical_history = db.Column(db.Text, nullable=True, comment='病史')
    current_symptoms = db.Column(db.Text, nullable=True, comment='当前症状')
    
    # 账户状态
    is_active = db.Column(db.Boolean, default=True, comment='账户是否激活')
    is_verified = db.Column(db.Boolean, default=False, comment='邮箱是否验证')
    role = db.Column(db.Enum('patient', 'doctor', 'admin'), default='patient', comment='用户角色')
    
    # 时间戳
    created_at = db.Column(db.DateTime, default=datetime.utcnow, comment='创建时间')
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, comment='更新时间')
    
    def __init__(self, username, email, password, **kwargs):
        """初始化用户"""
        self.username = username
        self.email = email
        self.set_password(password)
        
        # 设置其他属性
        for key, value in kwargs.items():
            if hasattr(self, key):
                setattr(self, key, value)
    
    def set_password(self, password):
        """设置密码哈希"""
        self.password_hash = generate_password_hash(password)
    
    def check_password(self, password):
        """验证密码"""
        return check_password_hash(self.password_hash, password)
    
    def to_dict(self, include_sensitive=False):
        """将用户对象转换为字典"""
        data = {
            'id': self.id,
            'username': self.username,
            'email': self.email,
            'full_name': self.full_name,
            'age': self.age,
            'gender': self.gender,
            'occupation': self.occupation,
            'phone': self.phone,
            'height': self.height,
            'weight': self.weight,
            'role': self.role,
            'is_active': self.is_active,
            'is_verified': self.is_verified,
            'profile_complete': bool(self.full_name and self.age is not None and self.gender),
            'profile_missing_fields': [label for value, label in [
                (bool(self.full_name), '姓名或称呼'), (self.age is not None, '年龄'),
                (bool(self.gender), '性别')] if not value],
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None
        }
        
        if include_sensitive:
            data['medical_history'] = self.medical_history
            data['current_symptoms'] = self.current_symptoms
        
        return data
    
    def update_profile(self, data):
        """更新用户资料"""
        allowed_fields = ['full_name', 'age', 'gender', 'occupation', 'phone', 
                         'height', 'weight', 'medical_history', 'current_symptoms']
        
        for field in allowed_fields:
            if field in data:
                setattr(self, field, data[field])
        
        self.updated_at = datetime.utcnow()
    
    @classmethod
    def create_sample_users(cls):
        """创建示例用户（用于测试）"""
        sample_users = [
            {
                'username': 'patient1',
                'email': 'patient1@example.com',
                'password': 'password123',
                'full_name': '张三',
                'age': 35,
                'gender': 'male',
                'occupation': '程序员',
                'role': 'patient'
            },
            {
                'username': 'doctor1',
                'email': 'doctor1@example.com',
                'password': 'password123',
                'full_name': '李医生',
                'age': 45,
                'gender': 'female',
                'occupation': '骨科医生',
                'role': 'doctor'
            },
            {
                'username': 'admin1',
                'email': 'admin1@example.com',
                'password': 'admin123',
                'full_name': '王管理员',
                'age': 30,
                'gender': 'male',
                'occupation': '系统管理员',
                'role': 'admin'
            }
        ]
        
        return sample_users
    
    def __repr__(self):
        return f'<User {self.username}>'
