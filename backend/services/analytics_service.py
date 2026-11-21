"""
分析服务
面向医生/机构的群体数据统计分析（分析群体健康状况，生成报告）
"""

from datetime import datetime, timedelta
from sqlalchemy import func, and_
from models.user import User
from models.assessment import Assessment
from utils.response import error

class AnalyticsService:
    """分析服务类"""
    
    @staticmethod
    def get_population_statistics():
        """获取群体统计信息"""
        try:
            # 统计用户总数
            total_users = User.query.count()
            total_patients = User.query.filter_by(role='patient').count()
            total_doctors = User.query.filter_by(role='doctor').count()
            
            # 统计评估总数
            total_assessments = Assessment.query.count()
            
            # 统计最近30天的活跃用户
            thirty_days_ago = datetime.utcnow() - timedelta(days=30)
            active_users = User.query.filter(
                User.last_login >= thirty_days_ago
            ).count()
            
            # 统计各分级比例
            from sqlalchemy import case
            grade_distribution = db.session.query(
                Assessment.grade,
                func.count(Assessment.id).label('count')
            ).filter(
                Assessment.grade.isnot(None)
            ).group_by(Assessment.grade).all()
            
            grade_stats = {grade: count for grade, count in grade_distribution}
            
            return {
                'user_statistics': {
                    'total_users': total_users,
                    'patients': total_patients,
                    'doctors': total_doctors,
                    'active_users': active_users,
                    'active_rate': round(active_users / total_users * 100, 2) if total_users > 0 else 0
                },
                'assessment_statistics': {
                    'total_assessments': total_assessments,
                    'avg_assessments_per_user': round(total_assessments / total_users, 2) if total_users > 0 else 0
                },
                'grade_distribution': grade_stats
            }, None
            
        except Exception as e:
            return None, error(f'获取群体统计失败: {str(e)}', 500)
    
    @staticmethod
    def get_age_distribution():
        """获取年龄分布"""
        try:
            # 按年龄段统计
            age_ranges = [
                (0, 18, '0-18岁'),
                (19, 30, '19-30岁'),
                (31, 45, '31-45岁'),
                (46, 60, '46-60岁'),
                (61, 100, '61岁以上')
            ]
            
            distribution = {}
            for min_age, max_age, label in age_ranges:
                count = User.query.filter(
                    and_(
                        User.age >= min_age,
                        User.age <= max_age,
                        User.role == 'patient'
                    )
                ).count()
                distribution[label] = count
            
            return distribution, None
            
        except Exception as e:
            return None, error(f'获取年龄分布失败: {str(e)}', 500)
    
    @staticmethod
    def get_occupation_distribution():
        """获取职业分布"""
        try:
            # 统计常见职业
            common_occupations = ['学生', '办公室职员', '程序员', '教师', '医生', '工人', '其他']
            
            distribution = {}
            for occupation in common_occupations:
                if occupation == '其他':
                    # 统计不在常见职业列表中的
                    count = User.query.filter(
                        and_(
                            User.occupation.isnot(None),
                            ~User.occupation.in_(common_occupations[:-1]),
                            User.role == 'patient'
                        )
                    ).count()
                else:
                    count = User.query.filter_by(occupation=occupation, role='patient').count()
                
                distribution[occupation] = count
            
            return distribution, None
            
        except Exception as e:
            return None, error(f'获取职业分布失败: {str(e)}', 500)
    
    @staticmethod
    def get_grade_trend_over_time(days=90):
        """获取分级趋势（随时间变化）"""
        try:
            end_date = datetime.utcnow().date()
            start_date = end_date - timedelta(days=days)
            
            # 按周分组统计
            weekly_stats = db.session.query(
                func.date_trunc('week', Assessment.assessment_date).label('week'),
                Assessment.grade,
                func.count(Assessment.id).label('count')
            ).filter(
                Assessment.assessment_date >= start_date,
                Assessment.assessment_date <= end_date,
                Assessment.grade.isnot(None)
            ).group_by(
                func.date_trunc('week', Assessment.assessment_date),
                Assessment.grade
            ).order_by('week').all()
            
            # 格式化结果
            trend_data = {}
            for week, grade, count in weekly_stats:
                week_str = week.strftime('%Y-%m-%d')
                if week_str not in trend_data:
                    trend_data[week_str] = {}
                trend_data[week_str][grade] = count
            
            return {
                'time_range': {
                    'start_date': start_date.isoformat(),
                    'end_date': end_date.isoformat(),
                    'days': days
                },
                'weekly_trend': trend_data
            }, None
            
        except Exception as e:
            return None, error(f'获取分级趋势失败: {str(e)}', 500)
    
    @staticmethod
    def generate_population_report():
        """生成群体健康报告"""
        try:
            # 获取各种统计数据
            pop_stats, err = AnalyticsService.get_population_statistics()
            if err:
                return None, err
            
            age_dist, err = AnalyticsService.get_age_distribution()
            if err:
                return None, err
            
            occ_dist, err = AnalyticsService.get_occupation_distribution()
            if err:
                return None, err
            
            grade_trend, err = AnalyticsService.get_grade_trend_over_time(30)
            if err:
                return None, err
            
            # 生成报告摘要
            total_assessments = pop_stats['assessment_statistics']['total_assessments']
            avg_grade = 0
            if pop_stats['grade_distribution']:
                grade_scores = {'normal': 1, 'mild': 2, 'moderate': 3, 'severe': 4}
                total_weighted = 0
                total_count = 0
                for grade, count in pop_stats['grade_distribution'].items():
                    if grade in grade_scores:
                        total_weighted += grade_scores[grade] * count
                        total_count += count
                avg_grade = round(total_weighted / total_count, 2) if total_count > 0 else 0
            
            # 分析主要问题
            main_issues = []
            if pop_stats['grade_distribution'].get('severe', 0) > 0:
                severe_percent = pop_stats['grade_distribution']['severe'] / total_assessments * 100
                if severe_percent > 10:
                    main_issues.append(f"重度颈椎问题比例较高 ({severe_percent:.1f}%)")
            
            if pop_stats['grade_distribution'].get('moderate', 0) > 0:
                moderate_percent = pop_stats['grade_distribution']['moderate'] / total_assessments * 100
                if moderate_percent > 30:
                    main_issues.append(f"中度颈椎问题普遍 ({moderate_percent:.1f}%)")
            
            # 生成建议
            recommendations = []
            if avg_grade > 2.5:
                recommendations.append("群体颈椎健康水平偏低，建议开展颈椎健康教育活动")
            
            # 找出高风险职业
            high_risk_occupations = []
            for occupation, count in occ_dist.items():
                if count > 10 and occupation in ['程序员', '办公室职员']:
                    high_risk_occupations.append(occupation)
            
            if high_risk_occupations:
                recommendations.append(f"{'、'.join(high_risk_occupations)}职业群体颈椎问题较为突出，建议针对性干预")
            
            return {
                'report_date': datetime.utcnow().isoformat(),
                'summary': {
                    'total_users': pop_stats['user_statistics']['total_users'],
                    'total_assessments': total_assessments,
                    'average_grade': avg_grade,
                    'active_rate': pop_stats['user_statistics']['active_rate']
                },
                'demographics': {
                    'age_distribution': age_dist,
                    'occupation_distribution': occ_dist
                },
                'health_status': {
                    'grade_distribution': pop_stats['grade_distribution'],
                    'main_issues': main_issues
                },
                'recommendations': recommendations,
                'trend_analysis': grade_trend['weekly_trend']
            }, None
            
        except Exception as e:
            return None, error(f'生成群体报告失败: {str(e)}', 500)
    
    @staticmethod
    def get_high_risk_patients(threshold_grade='moderate', limit=20):
        """获取高风险患者列表"""
        try:
            # 获取最近评估为指定分级或更差的患者
            subquery = db.session.query(
                Assessment.user_id,
                func.max(Assessment.assessment_date).label('latest_date')
            ).filter(
                Assessment.grade.isnot(None)
            ).group_by(Assessment.user_id).subquery()
            
            high_risk_patients = db.session.query(
                User, Assessment
            ).join(
                Assessment, User.id == Assessment.user_id
            ).join(
                subquery, and_(
                    Assessment.user_id == subquery.c.user_id,
                    Assessment.assessment_date == subquery.c.latest_date
                )
            ).filter(
                Assessment.grade.in_(['moderate', 'severe']) if threshold_grade == 'moderate' else ['severe']
            ).order_by(
                Assessment.grade_score.desc()
            ).limit(limit).all()
            
            result = []
            for user, assessment in high_risk_patients:
                result.append({
                    'patient': {
                        'id': user.id,
                        'username': user.username,
                        'age': user.age,
                        'occupation': user.occupation,
                        'last_login': user.last_login.isoformat() if user.last_login else None
                    },
                    'latest_assessment': {
                        'date': assessment.assessment_date.isoformat(),
                        'grade': assessment.grade,
                        'grade_score': assessment.grade_score,
                        'details': assessment.grade_details
                    }
                })
            
            return result, None
            
        except Exception as e:
            return None, error(f'获取高风险患者失败: {str(e)}', 500)

# 全局数据库实例
from models.user import db
