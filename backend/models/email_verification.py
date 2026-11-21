"""Persistent, single-use email challenges and shared authentication limits."""
from datetime import datetime

from models.user import db


class EmailVerification(db.Model):
    __tablename__ = 'email_verifications'

    id = db.Column(db.String(32), primary_key=True)
    email = db.Column(db.String(100), nullable=False, index=True)
    purpose = db.Column(db.String(16), nullable=False)
    subject = db.Column(db.String(100), nullable=False)
    code_hash = db.Column(db.String(64), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    expires_at = db.Column(db.DateTime, nullable=False, index=True)
    attempts = db.Column(db.Integer, default=0, nullable=False)
    consumed = db.Column(db.Boolean, default=False, nullable=False)
    delivered = db.Column(db.Boolean, default=False, nullable=False)


class AuthRateLimit(db.Model):
    __tablename__ = 'auth_rate_limits'

    key = db.Column(db.String(64), primary_key=True)
    count = db.Column(db.Integer, default=0, nullable=False)
    reset_at = db.Column(db.DateTime, nullable=False, index=True)
