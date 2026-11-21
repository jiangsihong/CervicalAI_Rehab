"""Camera posture sessions, kept separately from six-direction assessments."""
import json
from datetime import datetime, timedelta

from models.user import db


class CameraSession(db.Model):
    __tablename__ = 'camera_sessions'

    id = db.Column(db.String(36), primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False, index=True)
    started_at = db.Column(db.DateTime, nullable=False, index=True)
    revision = db.Column(db.Integer, nullable=False)
    payload = db.Column(db.Text, nullable=False)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    def to_dict(self, detail=True):
        data = json.loads(self.payload)
        # A browser that disappeared without a final save leaves a recoverable checkpoint.
        if data['status'] == 'recording' and self.updated_at < datetime.utcnow() - timedelta(minutes=2):
            data['status'] = 'interrupted'
        if not detail:
            data.pop('samples', None)
        return data
