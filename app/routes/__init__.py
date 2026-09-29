from app.routes.auth import auth_bp
from app.routes.dashboard import dashboard_bp
from app.routes.profile import profile_bp
from app.routes.activity import activity_bp
from app.routes.recommendations import recommendations_bp
from app.routes.progress import progress_bp
from app.routes.weekly_report import weekly_report_bp
from app.routes.assistant import assistant_bp
from app.routes.admin import admin_bp
from app.routes.api import api_bp

__all__ = [
    "auth_bp",
    "dashboard_bp",
    "profile_bp",
    "activity_bp",
    "recommendations_bp",
    "progress_bp",
    "weekly_report_bp",
    "assistant_bp",
    "admin_bp",
    "api_bp",
]
