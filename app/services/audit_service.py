"""
Audit Logging Service.
Records security and lifecycle events: authentication, profile changes, model deployments, and rollbacks.
"""

import json
from typing import Dict, Any, Optional
from flask import request
from app.extensions import db
from app.models.audit_log import AuditLog


class AuditService:
    @staticmethod
    def log_event(
        action: str,
        user_id: Optional[int] = None,
        details: Optional[Dict[str, Any]] = None,
        ip_address: Optional[str] = None
    ) -> AuditLog:
        if ip_address is None:
            try:
                ip_address = request.remote_addr
            except RuntimeError:
                ip_address = "127.0.0.1"

        entry = AuditLog(
            user_id=user_id,
            action=action,
            details_json=json.dumps(details or {}),
            ip_address=ip_address,
        )
        try:
            db.session.add(entry)
            db.session.commit()
        except Exception:
            db.session.rollback()
        return entry
