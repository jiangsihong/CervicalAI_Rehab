"""
数据库配置文件
配置MySQL数据库连接、JWT密钥等
"""

import os
from datetime import timedelta

class Config:
    """基础配置类"""
    # Flask配置
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'dev-secret-key-change-in-production'
    
    # 数据库配置 - 默认使用MySQL，仅保存用户注册信息
    DB_TYPE = os.environ.get('DB_TYPE') or 'mysql'  # 'mysql' 或 'sqlite'
    
    # SQLite配置（默认）
    SQLITE_DATABASE = os.environ.get('SQLITE_DATABASE') or 'cervicalai.db'
    SQLITE_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), SQLITE_DATABASE)
    
    # MySQL数据库配置（可选）
    MYSQL_HOST = os.environ.get('MYSQL_HOST') or '127.0.0.1'
    MYSQL_PORT = int(os.environ.get('MYSQL_PORT') or 3306)
    MYSQL_USER = os.environ.get('MYSQL_USER') or 'cervicalai_user'
    MYSQL_PASSWORD = os.environ.get('MYSQL_PASSWORD') or 'cervicalai_password'
    MYSQL_DATABASE = os.environ.get('MYSQL_DATABASE') or 'cervicalai_db'
    
    # SQLAlchemy配置
    if DB_TYPE == 'mysql':
        SQLALCHEMY_DATABASE_URI = f'mysql+pymysql://{MYSQL_USER}:{MYSQL_PASSWORD}@{MYSQL_HOST}:{MYSQL_PORT}/{MYSQL_DATABASE}'
    else:
        SQLALCHEMY_DATABASE_URI = f'sqlite:///{SQLITE_PATH}'
    
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SQLALCHEMY_ECHO = False  # 设置为True可以查看SQL语句
    
    # JWT配置
    JWT_SECRET_KEY = os.environ.get('JWT_SECRET_KEY') or 'jwt-secret-key-change-in-production'
    JWT_ACCESS_TOKEN_EXPIRES = timedelta(hours=24)
    JWT_REFRESH_TOKEN_EXPIRES = timedelta(days=30)
    
    # 应用配置
    DEBUG = os.environ.get('FLASK_DEBUG') or True
    TESTING = False
    
    # 文件上传配置
    MAX_CONTENT_LENGTH = 16 * 1024 * 1024  # 16MB
    UPLOAD_FOLDER = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'uploads')
    ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'mp4', 'avi', 'mov'}
    
    # 日志配置
    LOG_LEVEL = os.environ.get('LOG_LEVEL') or 'INFO'
    LOG_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'logs', 'app.log')

    # One configured sender can deliver to patients at any common email provider.
    MAIL_HOST = os.environ.get('MAIL_HOST', '')
    MAIL_PORT = int(os.environ.get('MAIL_PORT') or 465)
    MAIL_SECURITY = os.environ.get('MAIL_SECURITY', 'ssl')  # ssl or starttls
    MAIL_USERNAME = os.environ.get('MAIL_USERNAME', '')
    MAIL_PASSWORD = os.environ.get('MAIL_PASSWORD', '')
    MAIL_FROM = os.environ.get('MAIL_FROM') or MAIL_USERNAME


class DevelopmentConfig(Config):
    """开发环境配置"""
    DEBUG = True
    SQLALCHEMY_ECHO = True  # 开发环境下显示SQL语句


class TestingConfig(Config):
    """测试环境配置"""
    TESTING = True
    SQLALCHEMY_DATABASE_URI = 'sqlite:///:memory:'  # 测试使用内存数据库
    WTF_CSRF_ENABLED = False


class ProductionConfig(Config):
    """生产环境配置"""
    DEBUG = False
    TESTING = False
    # 生产环境应该从环境变量读取敏感信息
    SECRET_KEY = os.environ.get('SECRET_KEY')
    JWT_SECRET_KEY = os.environ.get('JWT_SECRET_KEY')
    
    # 生产环境默认使用MySQL
    DB_TYPE = os.environ.get('DB_TYPE') or 'mysql'
    
    # 生产环境MySQL配置
    MYSQL_HOST = os.environ.get('MYSQL_HOST')
    MYSQL_PORT = int(os.environ.get('MYSQL_PORT') or 3306)
    MYSQL_USER = os.environ.get('MYSQL_USER')
    MYSQL_PASSWORD = os.environ.get('MYSQL_PASSWORD')
    MYSQL_DATABASE = os.environ.get('MYSQL_DATABASE')
    
    # SQLAlchemy配置 - 生产环境默认使用MySQL
    if DB_TYPE == 'mysql':
        SQLALCHEMY_DATABASE_URI = f'mysql+pymysql://{MYSQL_USER}:{MYSQL_PASSWORD}@{MYSQL_HOST}:{MYSQL_PORT}/{MYSQL_DATABASE}'
    else:
        SQLITE_DATABASE = os.environ.get('SQLITE_DATABASE') or 'cervicalai.db'
        SQLITE_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), SQLITE_DATABASE)
        SQLALCHEMY_DATABASE_URI = f'sqlite:///{SQLITE_PATH}'


# 配置映射
config = {
    'development': DevelopmentConfig,
    'testing': TestingConfig,
    'production': ProductionConfig,
    'default': DevelopmentConfig
}
