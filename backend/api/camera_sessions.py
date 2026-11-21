"""Authenticated, idempotent camera-session storage and history."""
import json
import math
from datetime import datetime, timezone, timedelta
from uuid import UUID

from flask import Blueprint, request
from flask_jwt_extended import get_jwt_identity, jwt_required
from sqlalchemy.exc import SQLAlchemyError

from models.camera_session import CameraSession
from models.user import User, db
from utils.response import success, error

camera_sessions_bp = Blueprint('camera_sessions', __name__)
AXES = ('tilt', 'pan', 'roll')


def number(value, name, minimum, maximum, integer=False):
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
        raise ValueError(name + ' 必须是有效数字')
    if not minimum <= value <= maximum or (integer and int(value) != value):
        raise ValueError(name + ' 超出有效范围')
    return int(value) if integer else value


def timestamp(value):
    if not isinstance(value, str):
        raise ValueError('检测时间格式无效')
    parsed = datetime.fromisoformat(value.replace('Z', '+00:00'))
    if parsed.tzinfo is None:
        raise ValueError('检测时间必须包含时区')
    return parsed.astimezone(timezone.utc).replace(tzinfo=None)


def validate_payload(data, session_id):
    if not isinstance(data, dict):
        raise ValueError('检测记录格式无效')
    start = timestamp(data.get('started_at'))
    end = timestamp(data.get('ended_at')) if data.get('ended_at') else None
    status = data.get('status')
    if status not in ('recording', 'completed', 'interrupted'):
        raise ValueError('检测状态无效')
    if (status == 'recording' and end is not None) or (status != 'recording' and end is None):
        raise ValueError('检测结束时间与状态不一致')
    if end and end < start:
        raise ValueError('结束时间不能早于开始时间')
    duration = number(data.get('duration_seconds'), '持续时长', 0, 31536000)
    frames = number(data.get('frame_count'), '检测帧数', 0, 100000000, True)
    detected = number(data.get('detected_frames'), '有效帧数', 0, frames, True)
    stats = {}
    source_stats = data.get('angle_stats')
    if not isinstance(source_stats, dict):
        raise ValueError('角度统计格式无效')
    for axis in AXES:
        item = source_stats.get(axis)
        if item is None:
            stats[axis] = None
            continue
        if not isinstance(item, dict):
            raise ValueError('角度统计格式无效')
        count = number(item.get('count'), '角度样本数', 1, detected, True)
        low = number(item.get('min'), '最小角度', -180, 180)
        high = number(item.get('max'), '最大角度', low, 180)
        mean = number(item.get('mean'), '平均角度', low, high)
        stats[axis] = {'count': count, 'min': low, 'max': high, 'mean': mean}
    samples = data.get('samples')
    if not isinstance(samples, list) or len(samples) > 300:
        raise ValueError('角度曲线最多保存 300 个采样点')
    cleaned = []
    previous = 0
    for item in samples:
        if not isinstance(item, dict):
            raise ValueError('角度采样格式无效')
        elapsed = number(item.get('elapsed'), '采样时间', previous, duration)
        previous = elapsed
        point = {'elapsed': elapsed}
        for axis in AXES:
            point[axis] = None if item.get(axis) is None else number(item[axis], '采样角度', -180, 180)
        cleaned.append(point)
    return start, {
        'id': session_id, 'started_at': start.isoformat() + 'Z',
        'ended_at': end.isoformat() + 'Z' if end else None,
        'status': status, 'revision': number(data.get('revision'), '版本', 1, 100000000, True),
        'duration_seconds': duration, 'frame_count': frames, 'detected_frames': detected,
        'angle_stats': stats, 'samples': cleaned,
    }


@camera_sessions_bp.route('/<session_id>', methods=['PUT'])
@jwt_required()
def save_camera_session(session_id):
    try:
        session_id = str(UUID(session_id))
        user_id = int(get_jwt_identity())
        user = db.session.get(User, user_id)
        if not user or not user.is_active:
            return error('账号不可用', 403)
        start, payload = validate_payload(request.get_json(silent=True), session_id)
        record = db.session.get(CameraSession, session_id)
        if record and record.user_id != user_id:
            return error('记录不存在', 404)
        if record:
            if start != record.started_at:
                return error('检测开始时间不能修改', 400)
            if payload['revision'] <= record.revision:
                return success({'session': record.to_dict()})
            # Conditional update keeps delayed checkpoints from overwriting a newer final save.
            CameraSession.query.filter_by(id=session_id, user_id=user_id).filter(
                CameraSession.revision < payload['revision']
            ).update({'payload': json.dumps(payload), 'revision': payload['revision'],
                      'updated_at': datetime.utcnow()}, synchronize_session=False)
        else:
            record = CameraSession(id=session_id, user_id=user_id, started_at=start,
                                   revision=payload['revision'], payload=json.dumps(payload))
            db.session.add(record)
        db.session.commit()
        db.session.expire_all()
        return success({'session': db.session.get(CameraSession, session_id).to_dict()})
    except (ValueError, TypeError, OverflowError) as exc:
        return error(str(exc), 400)
    except SQLAlchemyError:
        db.session.rollback()
        return error('保存检测记录失败，请稍后重试', 500)


@camera_sessions_bp.route('', methods=['GET'])
@jwt_required()
def camera_history():
    try:
        limit = max(1, min(100, int(request.args.get('limit', 20))))
        offset = max(0, int(request.args.get('offset', 0)))
        query = CameraSession.query.filter_by(user_id=int(get_jwt_identity()))
        start, end = request.args.get('start_date'), request.args.get('end_date')
        # The browser sends its timezone offset, so date filters match displayed local dates.
        offset_minutes = int(request.args.get('timezone_offset', 0))
        if not -840 <= offset_minutes <= 840:
            raise ValueError('时区无效')
        if start:
            query = query.filter(CameraSession.started_at >= datetime.strptime(start, '%Y-%m-%d') + timedelta(minutes=offset_minutes))
        if end:
            query = query.filter(CameraSession.started_at < datetime.strptime(end, '%Y-%m-%d') + timedelta(days=1, minutes=offset_minutes))
        records = query.order_by(CameraSession.started_at.desc()).offset(offset).limit(limit).all()
        return success({'sessions': [item.to_dict(detail=False) for item in records],
                        'total': query.count(), 'limit': limit, 'offset': offset})
    except (ValueError, OverflowError):
        return error('分页或日期参数无效', 400)


@camera_sessions_bp.route('/<session_id>', methods=['GET'])
@jwt_required()
def camera_detail(session_id):
    record = CameraSession.query.filter_by(id=session_id, user_id=int(get_jwt_identity())).first()
    if not record:
        return error('记录不存在', 404)
    return success({'session': record.to_dict()})
