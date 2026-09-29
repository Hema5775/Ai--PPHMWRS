from datetime import datetime
from app.extensions import db


class SystemErrorLog(db.Model):
    """Structured application and ML error diagnostics log."""
    __tablename__ = "system_errors"

    id = db.Column(db.Integer, primary_key=True)
    error_id = db.Column(db.String(40), unique=True, nullable=False, index=True)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow, index=True)
    module = db.Column(db.String(60), nullable=False)
    endpoint = db.Column(db.String(120), nullable=True)
    severity = db.Column(db.String(20), nullable=False, default="ERROR")  # INFO, WARNING, ERROR, CRITICAL
    category = db.Column(db.String(30), nullable=False, default="BACKEND")
    # FRONTEND, BACKEND, DATABASE, ML, AUTHENTICATION, VALIDATION
    status = db.Column(db.String(20), nullable=False, default="OPEN")  # OPEN, RESOLVED, SUPPRESSED
    message = db.Column(db.Text, nullable=False)
    stack_trace = db.Column(db.Text, nullable=True)
    user_id = db.Column(db.Integer, nullable=True)
    model_version = db.Column(db.String(30), nullable=True)
    safe_user_message = db.Column(db.Text, nullable=False)

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "error_id": self.error_id,
            "timestamp": self.timestamp.isoformat() if self.timestamp else None,
            "module": self.module,
            "endpoint": self.endpoint,
            "severity": self.severity,
            "category": self.category,
            "status": self.status,
            "message": self.message,
            "user_id": self.user_id,
            "model_version": self.model_version,
            "safe_user_message": self.safe_user_message,
        }
