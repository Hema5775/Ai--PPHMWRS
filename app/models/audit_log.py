import json
from datetime import datetime
from app.extensions import db


class AuditLog(db.Model):
    """Audit log tracking significant system actions, ML lifecycle, and user interactions."""
    __tablename__ = "audit_logs"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, nullable=True, index=True)
    action = db.Column(db.String(60), nullable=False, index=True)
    details_json = db.Column(db.Text, default="{}")
    ip_address = db.Column(db.String(50), nullable=True)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow, index=True)

    def get_details(self) -> dict:
        try:
            return json.loads(self.details_json)
        except Exception:
            return {}

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "user_id": self.user_id,
            "action": self.action,
            "details": self.get_details(),
            "ip_address": self.ip_address,
            "timestamp": self.timestamp.isoformat() if self.timestamp else None,
        }
