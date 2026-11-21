"""
Flask应用入口
初始化API路由，连接数据库等
"""

import os
from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(os.path.abspath(__file__)), '.env'), override=False)
from flask import Flask
from flask_migrate import Migrate
from flask_jwt_extended import JWTManager
from flask_cors import CORS

from config import config
from models.user import db, User
from models.assessment import Assessment
from models.camera_session import CameraSession
from models.email_verification import EmailVerification, AuthRateLimit

def create_app(config_name='default'):
    """创建Flask应用工厂函数"""
    app = Flask(__name__)
    
    # 加载配置
    app.config.from_object(config[config_name])
    
    # 启用CORS
    CORS(app, resources={r"/api/*": {"origins": "*"}})
    
    # 初始化数据库
    db.init_app(app)
    
    # 初始化数据库迁移
    migrate = Migrate(app, db)
    
    # 初始化JWT
    jwt = JWTManager(app)
    
    # 创建上传目录
    os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
    os.makedirs(os.path.dirname(app.config['LOG_FILE']), exist_ok=True)
    
    # 补齐当前版本所需的数据表。create_all 是幂等操作，不会清空已有数据。
    ensure_database_schema(app)
    
    # 注册蓝图
    register_blueprints(app)
    
    # 注册命令行命令
    register_commands(app)
    
    # 注册错误处理器
    register_error_handlers(app)
    
    return app

def ensure_database_schema(app):
    """Create every registered application table that is still missing."""
    with app.app_context():
        db.create_all()

def register_blueprints(app):
    """注册蓝图（API路由）"""
    try:
        from api.user import user_bp
        from api.assessment import assessment_bp
        from api.camera_sessions import camera_sessions_bp
        
        app.register_blueprint(user_bp, url_prefix='/api/user')
        app.register_blueprint(assessment_bp, url_prefix='/api/assessment')
        app.register_blueprint(camera_sessions_bp, url_prefix='/api/assessment/pose/sessions')
        
        print("API蓝图已注册")
    except ImportError as e:
        print(f"注册蓝图时出错: {e}")
        print("请确保所有API模块都已创建")

def register_commands(app):
    """注册命令行命令"""
    @app.cli.command('init-db')
    def init_db():
        """重新初始化全部业务数据表"""
        with app.app_context():
            db.drop_all()
            db.create_all()
            print('用户与评估数据库已初始化')
    
    @app.cli.command('seed-db')
    def seed_db():
        """填充测试用户数据"""
        with app.app_context():
            # 创建示例用户
            sample_users = User.create_sample_users()
            for user_data in sample_users:
                if User.query.filter_by(username=user_data['username']).first():
                    continue
                user = User(
                    username=user_data['username'],
                    email=user_data['email'],
                    password=user_data['password']
                )
                # 设置其他属性
                for key in ['full_name', 'age', 'gender', 'occupation', 'role']:
                    if key in user_data:
                        setattr(user, key, user_data[key])
                
                db.session.add(user)
            
            db.session.commit()
            print('示例用户数据已填充')
    
    @app.cli.command('create-admin')
    def create_admin():
        """创建管理员用户"""
        with app.app_context():
            username = input('请输入管理员用户名: ')
            email = input('请输入管理员邮箱: ')
            password = input('请输入管理员密码: ')
            
            admin = User(
                username=username,
                email=email,
                password=password,
                role='admin',
                is_verified=True
            )
            
            db.session.add(admin)
            db.session.commit()
            print(f'管理员用户 {username} 已创建')

def register_error_handlers(app):
    """注册错误处理器"""
    @app.errorhandler(404)
    def not_found(error):
        return {'error': '资源未找到'}, 404
    
    @app.errorhandler(500)
    def internal_error(error):
        return {'error': '服务器内部错误'}, 500

# 创建应用实例
app = create_app()

if __name__ == '__main__':
    # Disable the Flask reloader because the spawned child process can lose the
    # Conda DLL PATH on Windows, which breaks imports such as ssl/_ssl.
    app.run(host='0.0.0.0', port=5000, debug=True, use_reloader=False)
