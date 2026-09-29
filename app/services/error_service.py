"""
Centralized Error Diagnostics and Bug Tracking Service.
Assigns unique traceable ERROR-IDs to system anomalies and logs them to the database and files.
"""

import uuid
import traceback
import logging
from typing import Optional
from flask import request
from app.extensions import db
from app.models.system_error import SystemErrorLog

logger = logging.getLogger("wellness.errors")


class ErrorTrackingService:
    @staticmethod
    def record_error(
        module: str,
        message: str,
        category: str = "BACKEND",
        severity: str = "ERROR",
        safe_user_message: str = "A temporary issue occurred. Your safe wellness plan is still active.",
        endpoint: Optional[str] = None,
        user_id: Optional[int] = None,
        model_version: Optional[str] = None,
        exc: Optional[Exception] = None
    ) -> str:
        prefix = {
            "ML": "ML-PRED",
            "DATABASE": "DB-ERR",
            "AUTHENTICATION": "AUTH-ERR",
            "VALIDATION": "VAL-ERR",
            "FRONTEND": "UI-ERR",
        }.get(category, "SYS-ERR")

        error_id = f"{prefix}-{uuid.uuid4().hex[:6].upper()}"
        stack = traceback.format_exc() if exc else ""

        if endpoint is None:
            try:
                endpoint = request.path
            except RuntimeError:
                endpoint = "CLI/Background"

        log_entry = SystemErrorLog(
            error_id=error_id,
            module=module,
            endpoint=endpoint,
            severity=severity,
            category=category,
            status="OPEN",
            message=message,
            stack_trace=stack,
            user_id=user_id,
            model_version=model_version,
            safe_user_message=safe_user_message,
        )

        try:
            db.session.add(log_entry)
            db.session.commit()
        except Exception as db_e:
            db.session.rollback()
            logger.critical(f"Failed to record system error to database: {db_e}")

        logger.error(f"[{error_id}] [{severity}] {module} ({endpoint}): {message}")
        return error_id
