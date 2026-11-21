"""
评估记录模型
存储颈椎评估数据，包括各方向最大角度、分级结果等
"""

from datetime import datetime
from .user import db

class Assessment(db.Model):
    """评估记录表模型"""
    __tablename__ = 'assessments'
    
    # 基本信息
    id = db.Column(db.Integer, primary_key=True, autoincrement=True, comment='评估记录ID')
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False, comment='用户ID')
    
    # 评估数据 - 各方向最大角度
    flexion_angle = db.Column(db.Float, nullable=True, comment='前屈角度')
    extension_angle = db.Column(db.Float, nullable=True, comment='后伸角度')
    left_lateral_flexion_angle = db.Column(db.Float, nullable=True, comment='左侧屈角度')
    right_lateral_flexion_angle = db.Column(db.Float, nullable=True, comment='右侧屈角度')
    left_rotation_angle = db.Column(db.Float, nullable=True, comment='左旋转角度')
    right_rotation_angle = db.Column(db.Float, nullable=True, comment='右旋转角度')
    
    # 颈椎健康四级分级结果
    grade = db.Column(db.Enum('normal', 'mild', 'moderate', 'severe'), nullable=True, comment='颈椎健康分级')
    grade_score = db.Column(db.Integer, nullable=True, comment='分级分数(1-4)')
    grade_details = db.Column(db.Text, nullable=True, comment='分级详情')
    
    # AI模型评估结果
    ai_confidence = db.Column(db.Float, nullable=True, comment='AI模型置信度')
    ai_recommendations = db.Column(db.Text, nullable=True, comment='AI建议')
    
    # 评估元数据
    assessment_date = db.Column(db.Date, nullable=False, comment='评估日期')
    assessment_duration = db.Column(db.Integer, nullable=True, comment='评估时长(秒)')
    device_info = db.Column(db.String(200), nullable=True, comment='设备信息')
    app_version = db.Column(db.String(20), nullable=True, comment='APP版本')
    
    # 文件路径（如果上传了视频/图片）
    video_path = db.Column(db.String(500), nullable=True, comment='视频文件路径')
    image_paths = db.Column(db.Text, nullable=True, comment='图片文件路径(JSON数组)')
    
    # 时间戳
    created_at = db.Column(db.DateTime, default=datetime.utcnow, comment='创建时间')
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, comment='更新时间')
    
    def __init__(self, user_id, assessment_date, **kwargs):
        """初始化评估记录"""
        self.user_id = user_id
        self.assessment_date = assessment_date
        
        # 设置其他属性
        for key, value in kwargs.items():
            if hasattr(self, key):
                setattr(self, key, value)
    
    def calculate_grade(self):
        """根据六方向颈椎活动角度计算四级健康分级"""
        from utils.grade_utils import calculate_grade_score

        grade, grade_score, details = calculate_grade_score({
            'flexion_angle': self.flexion_angle or 0,
            'extension_angle': self.extension_angle or 0,
            'left_lateral_flexion_angle': self.left_lateral_flexion_angle or 0,
            'right_lateral_flexion_angle': self.right_lateral_flexion_angle or 0,
            'left_rotation_angle': self.left_rotation_angle or 0,
            'right_rotation_angle': self.right_rotation_angle or 0,
        })

        self.grade = grade
        self.grade_score = grade_score
        self.grade_details = details
    
    def to_dict(self):
        """将评估记录转换为字典"""
        return {
            'id': self.id,
            'user_id': self.user_id,
            'flexion_angle': self.flexion_angle,
            'extension_angle': self.extension_angle,
            'left_lateral_flexion_angle': self.left_lateral_flexion_angle,
            'right_lateral_flexion_angle': self.right_lateral_flexion_angle,
            'left_rotation_angle': self.left_rotation_angle,
            'right_rotation_angle': self.right_rotation_angle,
            'grade': self.grade,
            'grade_score': self.grade_score,
            'grade_details': self.grade_details,
            'ai_confidence': self.ai_confidence,
            'ai_recommendations': self.ai_recommendations,
            'assessment_date': self.assessment_date.isoformat() if hasattr(self.assessment_date, 'isoformat') else str(self.assessment_date),
            'assessment_duration': self.assessment_duration,
            'device_info': self.device_info,
            'app_version': self.app_version,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None
        }
    
    @classmethod
    def create_sample_assessments(cls, user_id):
        """创建示例评估记录（用于测试）"""
        from datetime import date, timedelta
        
        sample_assessments = [
            {
                'user_id': user_id,
                'assessment_date': date.today() - timedelta(days=30),
                'flexion_angle': 55.5,
                'extension_angle': 48.2,
                'left_lateral_flexion_angle': 42.1,
                'right_lateral_flexion_angle': 43.8,
                'left_rotation_angle': 65.3,
                'right_rotation_angle': 64.7,
                'grade': 'mild',
                'grade_score': 2,
                'grade_details': '轻度颈椎活动受限，建议适当休息和颈部锻炼',
                'ai_confidence': 0.87,
                'assessment_duration': 120,
                'device_info': 'iPhone 13, iOS 16.0'
            },
            {
                'user_id': user_id,
                'assessment_date': date.today() - timedelta(days=15),
                'flexion_angle': 58.2,
                'extension_angle': 52.1,
                'left_lateral_flexion_angle': 45.3,
                'right_lateral_flexion_angle': 46.7,
                'left_rotation_angle': 68.4,
                'right_rotation_angle': 67.9,
                'grade': 'normal',
                'grade_score': 1,
                'grade_details': '颈椎活动度正常，继续保持良好习惯',
                'ai_confidence': 0.92,
                'assessment_duration': 110,
                'device_info': 'iPhone 13, iOS 16.1'
            },
            {
                'user_id': user_id,
                'assessment_date': date.today(),
                'flexion_angle': 60.1,
                'extension_angle': 55.3,
                'left_lateral_flexion_angle': 48.2,
                'right_lateral_flexion_angle': 49.1,
                'left_rotation_angle': 70.5,
                'right_rotation_angle': 69.8,
                'grade': 'normal',
                'grade_score': 1,
                'grade_details': '颈椎活动度良好，有明显改善',
                'ai_confidence': 0.95,
                'assessment_duration': 105,
                'device_info': 'iPhone 13, iOS 16.2'
            }
        ]
        
        return sample_assessments
    
    def __repr__(self):
        return f'<Assessment {self.id} for User {self.user_id}>'
