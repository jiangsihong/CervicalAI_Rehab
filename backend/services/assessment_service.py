"""
评估服务
数据落库、四级分级校验、生成趋势报告
"""

from datetime import datetime, timedelta
from models.assessment import Assessment, db
from utils.response import error

class AssessmentService:
    """评估服务类"""
    
    @staticmethod
    def submit_assessment_data(user_id, data):
        """提交评估数据"""
        try:
            # 验证必要字段
            if 'assessment_date' not in data:
                return None, error('缺少评估日期', 400)
            
            # 创建评估记录
            assessment = Assessment(
                user_id=user_id,
                assessment_date=datetime.strptime(data['assessment_date'], '%Y-%m-%d').date()
            )
            
            # 设置角度数据
            angle_fields = [
                'flexion_angle', 'extension_angle', 
                'left_lateral_flexion_angle', 'right_lateral_flexion_angle',
                'left_rotation_angle', 'right_rotation_angle'
            ]
            
            for field in angle_fields:
                if field in data:
                    setattr(assessment, field, float(data[field]))
            
            # 计算分级
            assessment.calculate_grade()
            
            # 设置其他字段
            optional_fields = [
                'ai_confidence', 'ai_recommendations',
                'assessment_duration', 'device_info', 'app_version',
                'video_path', 'image_paths'
            ]
            
            for field in optional_fields:
                if field in data:
                    setattr(assessment, field, data[field])
            
            db.session.add(assessment)
            db.session.commit()
            
            return assessment.to_dict(), None
            
        except Exception as e:
            db.session.rollback()
            return None, error(f'提交评估数据失败: {str(e)}', 500)
    
    @staticmethod
    def get_assessment_history(user_id, start_date=None, end_date=None, limit=50, offset=0):
        """获取评估历史"""
        try:
            # 构建查询
            query = Assessment.query.filter_by(user_id=user_id)
            
            if start_date:
                start = datetime.strptime(start_date, '%Y-%m-%d').date()
                query = query.filter(Assessment.assessment_date >= start)
            
            if end_date:
                end = datetime.strptime(end_date, '%Y-%m-%d').date()
                query = query.filter(Assessment.assessment_date <= end)
            
            # 按日期降序排序
            query = query.order_by(Assessment.assessment_date.desc())
            
            # 分页
            total = query.count()
            assessments = query.offset(offset).limit(limit).all()
            
            return {
                'assessments': [assessment.to_dict() for assessment in assessments],
                'total': total,
                'offset': offset,
                'limit': limit
            }, None
            
        except Exception as e:
            return None, error(f'获取评估历史失败: {str(e)}', 500)
    
    @staticmethod
    def calculate_grade_statistics(user_id):
        """计算分级统计"""
        try:
            # 获取所有评估记录
            assessments = Assessment.query.filter_by(user_id=user_id).all()
            
            if not assessments:
                return {
                    'total': 0,
                    'by_grade': {},
                    'average_grade': 0,
                    'improvement': 0
                }, None
            
            # 按分级统计
            grade_counts = {'normal': 0, 'mild': 0, 'moderate': 0, 'severe': 0}
            grade_scores = []
            
            for assessment in assessments:
                if assessment.grade:
                    grade_counts[assessment.grade] += 1
                if assessment.grade_score:
                    grade_scores.append(assessment.grade_score)
            
            # 计算平均分级
            average_grade = sum(grade_scores) / len(grade_scores) if grade_scores else 0
            
            # 计算改善情况（比较最早和最近的评估）
            sorted_assessments = sorted(assessments, key=lambda x: x.assessment_date)
            if len(sorted_assessments) >= 2:
                first = sorted_assessments[0]
                latest = sorted_assessments[-1]
                if first.grade_score and latest.grade_score:
                    improvement = first.grade_score - latest.grade_score  # 正数表示改善
                else:
                    improvement = 0
            else:
                improvement = 0
            
            return {
                'total': len(assessments),
                'by_grade': grade_counts,
                'average_grade': round(average_grade, 2),
                'improvement': improvement
            }, None
            
        except Exception as e:
            return None, error(f'计算分级统计失败: {str(e)}', 500)
    
    @staticmethod
    def generate_trend_report(user_id, days=30):
        """生成趋势报告"""
        try:
            end_date = datetime.utcnow().date()
            start_date = end_date - timedelta(days=days)
            
            # 查询该时间范围内的评估记录
            assessments = Assessment.query.filter(
                Assessment.user_id == user_id,
                Assessment.assessment_date >= start_date,
                Assessment.assessment_date <= end_date
            ).order_by(Assessment.assessment_date.asc()).all()
            
            if not assessments:
                return {
                    'time_range': {
                        'start_date': start_date.isoformat(),
                        'end_date': end_date.isoformat(),
                        'days': days
                    },
                    'assessments': [],
                    'summary': '暂无评估数据'
                }, None
            
            # 准备趋势数据
            trend_data = []
            for assessment in assessments:
                trend_data.append({
                    'date': assessment.assessment_date.isoformat(),
                    'grade': assessment.grade,
                    'grade_score': assessment.grade_score,
                    'flexion_angle': assessment.flexion_angle,
                    'extension_angle': assessment.extension_angle,
                    'left_lateral_flexion_angle': assessment.left_lateral_flexion_angle,
                    'right_lateral_flexion_angle': assessment.right_lateral_flexion_angle,
                    'left_rotation_angle': assessment.left_rotation_angle,
                    'right_rotation_angle': assessment.right_rotation_angle
                })
            
            # 生成报告摘要
            first = assessments[0]
            latest = assessments[-1]
            
            if first.grade_score and latest.grade_score:
                grade_change = first.grade_score - latest.grade_score
                if grade_change > 0:
                    grade_summary = f'改善{grade_change}级'
                elif grade_change < 0:
                    grade_summary = f'恶化{abs(grade_change)}级'
                else:
                    grade_summary = '保持稳定'
            else:
                grade_summary = '分级数据不足'
            
            # 计算角度变化
            angle_improvements = []
            angle_fields = ['flexion', 'extension', 'left_lateral', 'right_lateral', 'left_rotation', 'right_rotation']
            
            for field in angle_fields:
                first_angle = getattr(first, f'{field}_angle', 0) or 0
                latest_angle = getattr(latest, f'{field}_angle', 0) or 0
                if first_angle > 0 and latest_angle > 0:
                    change = latest_angle - first_angle
                    if change > 5:
                        angle_improvements.append(f'{field}角度增加{change:.1f}度')
            
            summary = f"在{len(assessments)}次评估中，颈椎健康{grade_summary}。"
            if angle_improvements:
                summary += f" 活动度改善明显的方向：{', '.join(angle_improvements)}。"
            
            return {
                'time_range': {
                    'start_date': start_date.isoformat(),
                    'end_date': end_date.isoformat(),
                    'days': days
                },
                'assessments': trend_data,
                'summary': summary,
                'statistics': {
                    'total_assessments': len(assessments),
                    'average_grade_score': sum(a.grade_score or 0 for a in assessments) / len(assessments),
                    'best_grade': min(a.grade_score or 4 for a in assessments),
                    'worst_grade': max(a.grade_score or 1 for a in assessments)
                }
            }, None
            
        except Exception as e:
            return None, error(f'生成趋势报告失败: {str(e)}', 500)
    
    @staticmethod
    def get_patient_assessments(patient_id, doctor_id):
        """获取患者的评估记录（医生查看）"""
        try:
            # 这里可以添加权限验证逻辑
            assessments = Assessment.query.filter_by(user_id=patient_id)\
                .order_by(Assessment.assessment_date.desc())\
                .limit(100)\
                .all()
            
            return {
                'assessments': [assessment.to_dict() for assessment in assessments],
                'total': len(assessments)
            }, None
            
        except Exception as e:
            return None, error(f'获取患者评估记录失败: {str(e)}', 500)
