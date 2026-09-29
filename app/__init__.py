"""
Application Factory module.
Configures structured logging, extensions, error handlers, and blueprints.
"""

import os
import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path
from flask import Flask, render_template, jsonify, request

from config import config_by_name
from app.extensions import db
from app.services.error_service import ErrorTrackingService


def create_app(config_name: str = "default") -> Flask:
    """Construct and configure the core Flask application instance."""
    app = Flask(
        __name__,
        template_folder="../templates",
        static_folder="../static",
    )

    # Load configuration
    if isinstance(config_name, type):
        cfg = config_name
    else:
        cfg = config_by_name.get(config_name, config_by_name["default"])
    app.config.from_object(cfg)

    # Ensure required runtime directories exist
    for directory in [app.config["LOG_DIR"], app.config["DATA_DIR"], app.config["MODEL_DIR"]]:
        Path(directory).mkdir(parents=True, exist_ok=True)

    # Setup structured logging
    _configure_logging(app)

    # Initialize extensions
    db.init_app(app)

    # Register blueprints
    _register_blueprints(app)

    # Register centralized error handlers
    _register_error_handlers(app)

    # Register template formatting filters
    _register_template_filters(app)

    # Template context processor for auth configuration
    @app.context_processor
    def inject_auth_config():
        return {
            "google_oauth_configured": bool(
                app.config.get("GOOGLE_CLIENT_ID") and app.config.get("GOOGLE_CLIENT_SECRET")
            ),
            "apple_oauth_configured": bool(
                app.config.get("APPLE_CLIENT_ID")
                and app.config.get("APPLE_TEAM_ID")
                and app.config.get("APPLE_KEY_ID")
                and app.config.get("APPLE_PRIVATE_KEY")
            ),
        }

    # Database initialization & safe migrations
    with app.app_context():
        try:
            db.create_all()
            _apply_migrations(app)
            app.logger.info("Database tables initialized successfully.")
        except Exception as e:
            app.logger.error(f"Database table initialization failed: {e}")

    return app


def _apply_migrations(app: Flask) -> None:
    """Safely apply non-destructive schema migrations for SQLite and PostgreSQL."""
    from sqlalchemy import inspect, text
    try:
        inspector = inspect(db.engine)
        tables = inspector.get_table_names()
        if "users" in tables:
            columns = [col["name"] for col in inspector.get_columns("users")]
            with db.engine.connect() as conn:
                changed = False
                if "google_id" not in columns:
                    conn.execute(text("ALTER TABLE users ADD COLUMN google_id VARCHAR(120)"))
                    changed = True
                if "apple_id" not in columns:
                    conn.execute(text("ALTER TABLE users ADD COLUMN apple_id VARCHAR(120)"))
                    changed = True
                if "phone_number" not in columns:
                    conn.execute(text("ALTER TABLE users ADD COLUMN phone_number VARCHAR(30)"))
                    changed = True
                if "auth_provider" not in columns:
                    conn.execute(text("ALTER TABLE users ADD COLUMN auth_provider VARCHAR(50) DEFAULT 'local'"))
                    changed = True
                if changed:
                    conn.commit()
                    app.logger.info("Database migration completed: schema updated non-destructively.")
    except Exception as e:
        app.logger.warning(f"Database schema migration check notice: {e}")


class SafeRotatingFileHandler(RotatingFileHandler):
    """RotatingFileHandler that gracefully handles Windows file lock conflicts during rollover."""
    def doRollover(self):
        try:
            super().doRollover()
        except (PermissionError, OSError):
            pass


def _configure_logging(app: Flask) -> None:
    if app.config.get("TESTING"):
        app.logger.setLevel(logging.INFO)
        return

    log_dir = Path(app.config["LOG_DIR"])
    formatter = logging.Formatter(
        "%(asctime)s [%(levelname)s] [%(name)s] [%(filename)s:%(lineno)d] %(message)s"
    )

    if not any(isinstance(h, RotatingFileHandler) for h in app.logger.handlers):
        # App logger file handler
        app_handler = SafeRotatingFileHandler(log_dir / "application.log", maxBytes=5 * 1024 * 1024, backupCount=5, delay=True)
        app_handler.setFormatter(formatter)
        app_handler.setLevel(logging.INFO)

        # Error logger file handler
        err_handler = SafeRotatingFileHandler(log_dir / "errors.log", maxBytes=5 * 1024 * 1024, backupCount=5, delay=True)
        err_handler.setFormatter(formatter)
        err_handler.setLevel(logging.ERROR)

        app.logger.addHandler(app_handler)
        app.logger.addHandler(err_handler)

    ml_logger = logging.getLogger("wellness.ml")
    if not any(isinstance(h, RotatingFileHandler) for h in ml_logger.handlers):
        ml_handler = SafeRotatingFileHandler(log_dir / "ml.log", maxBytes=5 * 1024 * 1024, backupCount=5, delay=True)
        ml_handler.setFormatter(formatter)
        ml_logger.addHandler(ml_handler)
        ml_logger.setLevel(logging.INFO)

    app.logger.setLevel(getattr(logging, app.config.get("LOG_LEVEL", "INFO")))


def _register_blueprints(app: Flask) -> None:
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

    app.register_blueprint(auth_bp)
    app.register_blueprint(dashboard_bp)
    app.register_blueprint(profile_bp)
    app.register_blueprint(activity_bp)
    app.register_blueprint(recommendations_bp)
    app.register_blueprint(progress_bp)
    app.register_blueprint(weekly_report_bp)
    app.register_blueprint(assistant_bp)
    app.register_blueprint(admin_bp)
    app.register_blueprint(api_bp)


def _register_error_handlers(app: Flask) -> None:
    """Centralized error handling avoiding raw 500s and exposing structured safe messages."""

    @app.errorhandler(400)
    def bad_request(e):
        if request.path.startswith("/api/"):
            return jsonify({"error": "BadRequest", "message": "The request was invalid or malformed."}), 400
        return render_template("base.html", error_message="Invalid request parameters."), 400

    @app.errorhandler(404)
    def not_found(e):
        if request.path.startswith("/api/"):
            return jsonify({"error": "NotFound", "message": "Requested resource was not found."}), 404
        return render_template("base.html", error_message="The requested page could not be found."), 404

    @app.errorhandler(422)
    def unprocessable_entity(e):
        if request.path.startswith("/api/"):
            return jsonify({"error": "UnprocessableEntity", "message": "Validation constraints failed."}), 422
        return render_template("base.html", error_message="Input validation failed."), 422

    @app.errorhandler(500)
    def internal_server_error(e):
        error_id = ErrorTrackingService.record_error(
            module="flask.core",
            message=str(e),
            category="BACKEND",
            severity="CRITICAL",
            safe_user_message="Our wellness system encountered an unexpected condition. Basic safe recommendations remain active.",
            endpoint=request.path,
            exc=e,
        )
        if request.path.startswith("/api/"):
            return jsonify({
                "error": "InternalServerError",
                "error_id": error_id,
                "message": "Personalization is temporarily adapting. Your basic wellness recommendations remain available.",
            }), 500
        return render_template(
            "base.html",
            error_id=error_id,
            error_message="Something went wrong while processing your request. Your safe wellness plan is still active.",
        ), 500


def _register_template_filters(app: Flask) -> None:
    """Register custom Jinja filters for clean number and unit formatting."""

    @app.template_filter("format_number")
    def format_number(val):
        if val is None or val == "":
            return "--"
        try:
            return f"{int(round(float(val))):,}"
        except (ValueError, TypeError):
            return str(val)

    @app.template_filter("format_decimal")
    def format_decimal(val, precision=1):
        if val is None or val == "":
            return "--"
        try:
            f_val = round(float(val), precision)
            if precision == 0:
                return str(int(f_val))
            # Format cleanly removing trailing zeros if clean float
            formatted = f"{f_val:.{precision}f}"
            return formatted.rstrip('0').rstrip('.') if '.' in formatted and precision > 1 else formatted
        except (ValueError, TypeError):
            return str(val)

    @app.template_filter("format_percent")
    def format_percent(val, precision=0):
        if val is None or val == "":
            return "--"
        try:
            f_val = float(val)
            if f_val <= 1.0 and f_val > 0.0:
                f_val = f_val * 100.0
            if precision == 0:
                return f"{int(round(f_val))}%"
            return f"{round(f_val, precision):.{precision}f}%"
        except (ValueError, TypeError):
            return str(val)
