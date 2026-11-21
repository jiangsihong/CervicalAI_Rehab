"""
评估API路由
接收移动端评估数据、查询历史记录、获取趋势图表数据
"""

from flask import Blueprint, Response, request
from flask_jwt_extended import jwt_required, get_jwt_identity
from datetime import datetime, timedelta
from urllib.parse import urlencode
import cv2
import html
import json
import time

from models.assessment import Assessment, db
from models.user import User
from services.pose_estimator_service import pose_estimator_service
from utils.response import success, error

# 创建蓝图
assessment_bp = Blueprint('assessment', __name__, url_prefix='/api/assessment')

def _parse_confidence_threshold():
    threshold_arg = request.args.get('confidence_threshold')
    if threshold_arg in (None, ''):
        return None, None

    try:
        threshold = float(threshold_arg)
    except ValueError:
        return None, 'confidence_threshold 必须是 0 到 1 之间的数字'

    if threshold < 0 or threshold > 1:
        return None, 'confidence_threshold 必须在 0 到 1 之间'

    return threshold, None


@assessment_bp.route('/pose/status', methods=['GET'])
def get_pose_model_status():
    """查看姿态估计模型权重路径和加载状态"""
    return success({
        'pose_model': pose_estimator_service.model_status()
    })

@assessment_bp.route('/pose/image', methods=['POST'])
def estimate_pose_from_image():
    """从上传图片或本地图片路径估计颈椎倾角"""
    try:
        draw = request.args.get('annotated', 'true').lower() != 'false'
        confidence_threshold, threshold_error = _parse_confidence_threshold()
        if threshold_error:
            return error(threshold_error, 400)

        image_file = request.files.get('image')
        if image_file and image_file.filename:
            result = pose_estimator_service.estimate_image_bytes(
                image_file.read(),
                draw=draw,
                confidence_threshold=confidence_threshold
            )
            source = {'type': 'upload', 'filename': image_file.filename}
        else:
            data = request.get_json(silent=True) or {}
            image_path = data.get('image_path')
            if not image_path:
                return error('请上传 image 文件，或在 JSON 中提供 image_path', 400)

            result = pose_estimator_service.estimate_image_path(
                image_path,
                draw=draw,
                confidence_threshold=confidence_threshold
            )
            source = {'type': 'path', 'image_path': image_path}

        annotated_frame = result.pop('annotated_frame', None)
        if annotated_frame is not None:
            result['annotated_image'] = pose_estimator_service.encode_annotated_image(annotated_frame)

        result['source'] = source
        return success(result)

    except FileNotFoundError as exc:
        return error(str(exc), 500)
    except ValueError as exc:
        return error(str(exc), 400)
    except Exception as exc:
        return error(f'姿态估计失败: {str(exc)}', 500)

@assessment_bp.route('/pose/camera/stream', methods=['GET'])
def stream_camera_pose():
    """打开服务端摄像头并以 MJPEG 实时显示颈椎倾角"""
    camera_arg = request.args.get('camera', '0')
    camera_source = int(camera_arg) if camera_arg.isdigit() else camera_arg
    confidence_threshold, threshold_error = _parse_confidence_threshold()
    if threshold_error:
        return error(threshold_error, 400)

    capture = cv2.VideoCapture(camera_source)
    if not capture.isOpened():
        return error(f'无法打开摄像头: {camera_arg}', 400)

    def generate_frames():
        try:
            while True:
                ok, frame = capture.read()
                if not ok:
                    break

                try:
                    result = pose_estimator_service.estimate_frame(
                        frame,
                        draw=True,
                        confidence_threshold=confidence_threshold
                    )
                    annotated = result.get('annotated_frame', frame)
                    if result.get('detection_count', 0) == 0:
                        pose_estimator_service.draw_no_detection(annotated)
                except Exception as exc:
                    annotated = frame
                    cv2.putText(
                        annotated,
                        f"Pose error: {str(exc)[:80]}",
                        (20, 40),
                        cv2.FONT_HERSHEY_DUPLEX,
                        0.6,
                        (0, 0, 255),
                        1,
                        lineType=cv2.LINE_AA,
                    )

                encoded, buffer = cv2.imencode('.jpg', annotated)
                if not encoded:
                    continue

                yield (
                    b'--frame\r\n'
                    b'Content-Type: image/jpeg\r\n\r\n' + buffer.tobytes() + b'\r\n'
                )
        finally:
            capture.release()

    return Response(generate_frames(), mimetype='multipart/x-mixed-replace; boundary=frame')

@assessment_bp.route('/pose/camera/status', methods=['GET'])
def stream_camera_pose_status():
    """打开服务端摄像头，并以 SSE 实时返回角度和健康状态 JSON。"""
    camera_arg = request.args.get('camera', '0')
    camera_source = int(camera_arg) if camera_arg.isdigit() else camera_arg
    confidence_threshold, threshold_error = _parse_confidence_threshold()
    if threshold_error:
        return error(threshold_error, 400)
    fps_arg = request.args.get('fps', '5')

    try:
        fps = max(1.0, min(float(fps_arg), 15.0))
    except ValueError:
        return error('fps 必须是数字', 400)

    capture = cv2.VideoCapture(camera_source)
    if not capture.isOpened():
        return error(f'无法打开摄像头: {camera_arg}', 400)

    def generate_status():
        frame_interval = 1.0 / fps
        try:
            while True:
                ok, frame = capture.read()
                if not ok:
                    payload = {
                        'success': False,
                        'message': '摄像头读取失败',
                        'camera': {'source': camera_arg},
                    }
                    yield f"event: error\ndata: {json.dumps(payload, ensure_ascii=False)}\n\n"
                    break

                try:
                    result = pose_estimator_service.estimate_frame(
                        frame,
                        draw=False,
                        confidence_threshold=confidence_threshold
                    )
                    payload = pose_estimator_service.to_json_payload(result)
                    payload['camera'] = {
                        'source': camera_arg,
                        'fps': fps,
                    }
                    payload['success'] = True
                    yield f"data: {json.dumps(payload, ensure_ascii=False)}\n\n"
                except Exception as exc:
                    payload = {
                        'success': False,
                        'message': f'姿态估计失败: {str(exc)}',
                        'camera': {'source': camera_arg},
                    }
                    yield f"event: error\ndata: {json.dumps(payload, ensure_ascii=False)}\n\n"

                time.sleep(frame_interval)
        finally:
            capture.release()

    return Response(generate_status(), mimetype='text/event-stream')

@assessment_bp.route('/pose/camera/view', methods=['GET'])
def view_camera_pose():
    """浏览器预览页面：显示服务端摄像头实时倾角画面"""
    camera_arg = request.args.get('camera', '0')
    stream_params = {'camera': camera_arg}
    threshold_arg = request.args.get('confidence_threshold')
    if threshold_arg:
        stream_params['confidence_threshold'] = threshold_arg
    stream_url = '/api/assessment/pose/camera/stream?' + urlencode(stream_params)
    status_url = '/api/assessment/pose/camera/status?' + urlencode(stream_params)
    safe_stream_url = html.escape(stream_url, quote=True)
    safe_status_url = html.escape(status_url, quote=True)
    page = f"""<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>颈椎倾角实时检测</title>
  <style>
    body {{
      margin: 0;
      background: #101418;
      color: #f4f7fb;
      font-family: Arial, "Microsoft YaHei", sans-serif;
    }}
    main {{
      min-height: 100vh;
      display: grid;
      place-items: center;
      padding: 24px;
      box-sizing: border-box;
    }}
    img {{
      width: min(100%, 1120px);
      max-height: 86vh;
      object-fit: contain;
      border: 1px solid #2a3440;
      background: #000;
    }}
    output {{
      display: block;
      width: min(100%, 1120px);
      margin-top: 12px;
      color: #c7d2df;
      font-size: 14px;
      line-height: 1.5;
      white-space: pre-wrap;
    }}
  </style>
</head>
<body>
  <main>
    <img src="{safe_stream_url}" alt="颈椎倾角实时检测画面">
    <output id="pose-status">正在读取实时状态...</output>
  </main>
  <script>
    const output = document.getElementById('pose-status');
    const source = new EventSource('{safe_status_url}');
    source.onmessage = (event) => {{
      const data = JSON.parse(event.data);
      const summary = data.summary;
      if (summary && !summary.detected) {{
        output.textContent = summary.message;
        return;
      }}
      if (summary && summary.detected) {{
        output.textContent = `TILT: ${{summary.tilt_degrees}}°, PAN: ${{summary.pan_degrees}}°\\n状态: ${{summary.health_level}} - ${{summary.health_message}}`;
        return;
      }}
      const primary = data.primary_detection;
      if (!primary) {{
        output.textContent = '未检测到头部';
        return;
      }}
      const angles = primary.cervical_angles;
      const health = primary.health_status;
      output.textContent = `TILT: ${{angles.raw_tilt}}°, PAN: ${{angles.raw_pan}}°\\n状态: ${{health.level}} - ${{health.message}}`;
    }};
    source.onerror = () => {{
      output.textContent = '实时状态连接中断';
    }};
  </script>
</body>
</html>"""
    return Response(page, mimetype='text/html')

@assessment_bp.route('/submit', methods=['POST'])
@jwt_required()
def submit_assessment():
    """提交评估数据"""
    try:
        user_id = get_jwt_identity()
        data = request.get_json(silent=True)

        if not isinstance(data, dict):
            return error('请求体必须是 JSON 对象', 400)
        
        # 验证必要字段
        if not data.get('assessment_date'):
            return error('缺少评估日期', 400)

        try:
            assessment_date = datetime.strptime(data['assessment_date'], '%Y-%m-%d').date()
        except (TypeError, ValueError):
            return error('评估日期格式应为 YYYY-MM-DD', 400)
        
        # 创建评估记录
        assessment = Assessment(
            user_id=user_id,
            assessment_date=assessment_date
        )
        
        # 设置角度数据
        angle_limits = {
            'flexion_angle': 90,
            'extension_angle': 90,
            'left_lateral_flexion_angle': 60,
            'right_lateral_flexion_angle': 60,
            'left_rotation_angle': 90,
            'right_rotation_angle': 90,
        }
        angle_fields = list(angle_limits)
        
        for field in angle_fields:
            if field not in data or data[field] in (None, ''):
                continue
            try:
                angle = float(data[field])
            except (TypeError, ValueError):
                return error(f'{field} 必须是数字', 400)
            if angle < 0 or angle > angle_limits[field]:
                return error(f'{field} 必须在 0 到 {angle_limits[field]} 度之间', 400)
            setattr(assessment, field, angle)
        
        # 计算分级（如果提供了角度数据）
        if any(field in data for field in angle_fields):
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
        
        return success({
            'message': '评估数据提交成功',
            'assessment': assessment.to_dict()
        }, code=201)
        
    except Exception as e:
        db.session.rollback()
        return error(f'提交评估数据失败: {str(e)}', 500)

@assessment_bp.route('/history', methods=['GET'])
@jwt_required()
def get_assessment_history():
    """获取评估历史记录"""
    try:
        user_id = get_jwt_identity()
        
        # 获取查询参数
        start_date = request.args.get('start_date')
        end_date = request.args.get('end_date')
        limit = int(request.args.get('limit', 50))
        offset = int(request.args.get('offset', 0))
        
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
        
        return success({
            'assessments': [assessment.to_dict() for assessment in assessments],
            'total': total,
            'offset': offset,
            'limit': limit
        })
        
    except Exception as e:
        return error(f'获取评估历史失败: {str(e)}', 500)

@assessment_bp.route('/<int:assessment_id>', methods=['GET'])
@jwt_required()
def get_assessment_detail(assessment_id):
    """获取评估详情"""
    try:
        user_id = get_jwt_identity()
        
        assessment = Assessment.query.get(assessment_id)
        
        if not assessment:
            return error('评估记录不存在', 404)
        
        # 检查权限（只能查看自己的评估记录，除非是医生或管理员）
        current_user = User.query.get(user_id)
        if assessment.user_id != int(user_id) and current_user.role not in ['doctor', 'admin']:
            return error('权限不足', 403)
        
        return success({
            'assessment': assessment.to_dict()
        })
        
    except Exception as e:
        return error(f'获取评估详情失败: {str(e)}', 500)

@assessment_bp.route('/trend', methods=['GET'])
@jwt_required()
def get_assessment_trend():
    """获取评估趋势数据"""
    try:
        user_id = get_jwt_identity()
        
        # 获取时间范围（默认最近30天）
        days = int(request.args.get('days', 30))
        end_date = datetime.utcnow().date()
        start_date = end_date - timedelta(days=days)
        
        # 查询该时间范围内的评估记录
        assessments = Assessment.query.filter(
            Assessment.user_id == user_id,
            Assessment.assessment_date >= start_date,
            Assessment.assessment_date <= end_date
        ).order_by(Assessment.assessment_date.asc()).all()
        
        # 准备趋势数据
        dates = []
        grades = []
        angles = {
            'flexion': [],
            'extension': [],
            'left_lateral': [],
            'right_lateral': [],
            'left_rotation': [],
            'right_rotation': []
        }
        
        grade_mapping = {'normal': 1, 'mild': 2, 'moderate': 3, 'severe': 4}
        
        for assessment in assessments:
            dates.append(assessment.assessment_date.isoformat())
            
            # 分级分数
            if assessment.grade:
                grades.append(grade_mapping.get(assessment.grade, 0))
            else:
                grades.append(0)
            
            # 角度数据
            angles['flexion'].append(assessment.flexion_angle or 0)
            angles['extension'].append(assessment.extension_angle or 0)
            angles['left_lateral'].append(assessment.left_lateral_flexion_angle or 0)
            angles['right_lateral'].append(assessment.right_lateral_flexion_angle or 0)
            angles['left_rotation'].append(assessment.left_rotation_angle or 0)
            angles['right_rotation'].append(assessment.right_rotation_angle or 0)
        
        # 计算统计数据
        if assessments:
            latest = assessments[-1]
            first = assessments[0] if len(assessments) > 1 else latest
            
            # 计算改善情况
            improvement = {}
            if first.grade_score and latest.grade_score:
                improvement['grade'] = first.grade_score - latest.grade_score
            
            # 计算角度变化
            for angle_type in ['flexion', 'extension', 'left_lateral', 'right_lateral', 'left_rotation', 'right_rotation']:
                first_angle = getattr(first, f'{angle_type}_angle', 0) or 0
                latest_angle = getattr(latest, f'{angle_type}_angle', 0) or 0
                if first_angle > 0 and latest_angle > 0:
                    improvement[f'{angle_type}_improvement'] = latest_angle - first_angle
        else:
            latest = None
            improvement = {}
        
        return success({
            'trend': {
                'dates': dates,
                'grades': grades,
                'angles': angles
            },
            'latest_assessment': latest.to_dict() if latest else None,
            'improvement': improvement,
            'time_range': {
                'start_date': start_date.isoformat(),
                'end_date': end_date.isoformat(),
                'days': days
            }
        })
        
    except Exception as e:
        return error(f'获取趋势数据失败: {str(e)}', 500)

@assessment_bp.route('/summary', methods=['GET'])
@jwt_required()
def get_assessment_summary():
    """获取评估摘要"""
    try:
        user_id = get_jwt_identity()
        
        # 获取总评估次数
        total_assessments = Assessment.query.filter_by(user_id=user_id).count()
        
        # 获取最近一次评估
        latest_assessment = Assessment.query.filter_by(user_id=user_id)\
            .order_by(Assessment.assessment_date.desc())\
            .first()
        
        # 获取最佳和最差评估
        best_assessment = Assessment.query.filter_by(user_id=user_id)\
            .filter(Assessment.grade_score.isnot(None))\
            .order_by(Assessment.grade_score.asc())\
            .first()
        
        worst_assessment = Assessment.query.filter_by(user_id=user_id)\
            .filter(Assessment.grade_score.isnot(None))\
            .order_by(Assessment.grade_score.desc())\
            .first()
        
        # 计算平均角度
        avg_angles = {}
        angle_fields = [
            'flexion_angle', 'extension_angle', 
            'left_lateral_flexion_angle', 'right_lateral_flexion_angle',
            'left_rotation_angle', 'right_rotation_angle'
        ]
        
        for field in angle_fields:
            from sqlalchemy import func
            avg_value = db.session.query(func.avg(getattr(Assessment, field)))\
                .filter_by(user_id=user_id)\
                .scalar()
            avg_angles[field.replace('_angle', '')] = float(avg_value) if avg_value else 0
        
        return success({
            'total_assessments': total_assessments,
            'latest_assessment': latest_assessment.to_dict() if latest_assessment else None,
            'best_assessment': best_assessment.to_dict() if best_assessment else None,
            'worst_assessment': worst_assessment.to_dict() if worst_assessment else None,
            'average_angles': avg_angles
        })
        
    except Exception as e:
        return error(f'获取评估摘要失败: {str(e)}', 500)

@assessment_bp.route('/patient/<int:patient_id>', methods=['GET'])
@jwt_required()
def get_patient_assessments(patient_id):
    """获取患者的评估记录（医生权限）"""
    try:
        user_id = get_jwt_identity()
        current_user = User.query.get(user_id)
        
        # 检查权限（必须是医生或管理员）
        if current_user.role not in ['doctor', 'admin']:
            return error('权限不足', 403)
        
        # 检查患者是否存在
        patient = User.query.get(patient_id)
        if not patient or patient.role != 'patient':
            return error('患者不存在', 404)
        
        # 获取评估记录
        assessments = Assessment.query.filter_by(user_id=patient_id)\
            .order_by(Assessment.assessment_date.desc())\
            .limit(100)\
            .all()
        
        return success({
            'patient': patient.to_dict(),
            'assessments': [assessment.to_dict() for assessment in assessments],
            'total': len(assessments)
        })
        
    except Exception as e:
        return error(f'获取患者评估记录失败: {str(e)}', 500)
