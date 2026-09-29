"""
Administrative and Model Governance Blueprint.
Provides admin dashboards for ML model health, versioning, rollback, retraining, and system error tracking.
"""

from pathlib import Path
from flask import Blueprint, render_template, request, redirect, url_for, flash, g, jsonify, current_app
from app.extensions import db
from app.routes.auth import admin_required
from app.models.user import User
from app.models.activity import DailyActivity
from app.models.model_version import ModelVersion
from app.models.system_error import SystemErrorLog
from app.models.audit_log import AuditLog
from app.ml.model_registry import ModelRegistry
from app.ml.model_health import ModelHealthMonitor
from app.ml.drift_detection import DriftDetector
from app.services.audit_service import AuditService

admin_bp = Blueprint("admin", __name__, url_prefix="/admin")


@admin_bp.route("/")
@admin_required
def index():
    user_count = User.query.count()
    activity_count = DailyActivity.query.count()
    error_count = SystemErrorLog.query.filter_by(status="OPEN").count()

    reg_path = current_app.config["REGISTRY_PATH"]
    prod_dir = current_app.config["MODEL_DIR"]
    registry = ModelRegistry(registry_file=reg_path, model_dir=prod_dir)

    active_meta = registry.get_active_model_meta("recommendation_model")
    loaded = registry.load_active_model_and_preprocessor("recommendation_model")

    health_status = loaded.get("status", "UNKNOWN")

    recent_errors = SystemErrorLog.query.order_by(SystemErrorLog.timestamp.desc()).limit(5).all()
    recent_audits = AuditLog.query.order_by(AuditLog.timestamp.desc()).limit(5).all()

    return render_template(
        "admin/index.html",
        user_count=user_count,
        activity_count=activity_count,
        error_count=error_count,
        active_meta=active_meta,
        health_status=health_status,
        recent_errors=recent_errors,
        recent_audits=recent_audits,
    )


@admin_bp.route("/database")
@admin_required
def database():
    """Database Administration and Inspection view (Requirement 20)."""
    from app.models.health_profile import HealthProfile
    from app.models.recommendation import Recommendation
    from app.models.task import DailyTask
    from app.models.wellness_score import WellnessScore
    from app.models.weekly_report import WeeklyReport

    models_map = {
        "users": (User, User.query.order_by(User.id.desc()).limit(50).all()),
        "health_profiles": (HealthProfile, HealthProfile.query.order_by(HealthProfile.id.desc()).limit(50).all()),
        "daily_activities": (DailyActivity, DailyActivity.query.order_by(DailyActivity.id.desc()).limit(50).all()),
        "wellness_scores": (WellnessScore, WellnessScore.query.order_by(WellnessScore.id.desc()).limit(50).all()),
        "recommendations": (Recommendation, Recommendation.query.order_by(Recommendation.id.desc()).limit(50).all()),
        "daily_tasks": (DailyTask, DailyTask.query.order_by(DailyTask.id.desc()).limit(50).all()),
        "weekly_reports": (WeeklyReport, WeeklyReport.query.order_by(WeeklyReport.id.desc()).limit(50).all()),
        "model_versions": (ModelVersion, ModelVersion.query.order_by(ModelVersion.id.desc()).limit(50).all()),
        "system_errors": (SystemErrorLog, SystemErrorLog.query.order_by(SystemErrorLog.id.desc()).limit(50).all()),
        "audit_logs": (AuditLog, AuditLog.query.order_by(AuditLog.id.desc()).limit(50).all()),
    }

    counts = {
        table_name: entry[0].query.count() for table_name, entry in models_map.items()
    }

    selected_table = request.args.get("table", "users")
    if selected_table not in models_map:
        selected_table = "users"

    records = [r.to_dict() if hasattr(r, "to_dict") else vars(r) for r in models_map[selected_table][1]]
    columns = list(records[0].keys()) if records else []

    return render_template(
        "admin/database.html",
        counts=counts,
        selected_table=selected_table,
        records=records,
        columns=columns,
    )


@admin_bp.route("/models")
@admin_required
def models():
    reg_path = current_app.config["REGISTRY_PATH"]
    prod_dir = current_app.config["MODEL_DIR"]
    registry = ModelRegistry(registry_file=reg_path, model_dir=prod_dir)

    active_meta = registry.get_active_model_meta("recommendation_model")
    all_models = registry.get_all_models()

    return render_template(
        "admin/models.html",
        active_meta=active_meta,
        all_models=all_models,
    )


@admin_bp.route("/model-health")
@admin_required
def model_health():
    reg_path = current_app.config["REGISTRY_PATH"]
    prod_dir = current_app.config["MODEL_DIR"]
    registry = ModelRegistry(registry_file=reg_path, model_dir=prod_dir)

    loaded = registry.load_active_model_and_preprocessor("recommendation_model")
    active_meta = registry.get_active_model_meta("recommendation_model")

    artifact_path = Path(active_meta["artifact_path"]) if (active_meta and active_meta.get("artifact_path")) else None

    # Run complete 11 checks
    health_report = ModelHealthMonitor.run_health_checks(
        model_name="recommendation_model",
        model_artifact=loaded.get("model"),
        preprocessor_artifact=loaded.get("preprocessor"),
        meta=active_meta,
        model_file_path=artifact_path,
    )

    # Drift check across recent database activity entries
    recent_acts = DailyActivity.query.order_by(DailyActivity.id.desc()).limit(30).all()
    drift_report = {"status": "HEALTHY", "message": "Baseline verified"}
    if active_meta and active_meta.get("baseline_stats") and recent_acts:
        detector = DriftDetector(baseline_stats=active_meta.get("baseline_stats"))
        sample_dicts = []
        for a in recent_acts:
            prof = a.user.profile if a.user else None
            sample_dicts.append({
                "age": prof.age if prof else 30,
                "bmi": prof.bmi if prof else 22.0,
                "avg_daily_steps": a.steps,
                "avg_sleep_duration": a.sleep_hours,
                "avg_water_intake": a.water_liters,
                "avg_exercise_minutes": a.exercise_minutes,
            })
        drift_report = detector.check_batch_drift(sample_dicts)

    return render_template(
        "admin/model_health.html",
        health=health_report,
        drift=drift_report,
        meta=active_meta,
    )


@admin_bp.route("/errors")
@admin_required
def errors():
    page = request.args.get("page", 1, type=int)
    category = request.args.get("category", "")
    query = SystemErrorLog.query
    if category:
        query = query.filter_by(category=category)

    error_logs = query.order_by(SystemErrorLog.timestamp.desc()).paginate(page=page, per_page=20)
    return render_template("admin/errors.html", errors=error_logs, current_category=category)


@admin_bp.route("/system-health")
@admin_required
def system_health():
    reg_path = current_app.config["REGISTRY_PATH"]
    prod_dir = current_app.config["MODEL_DIR"]
    registry = ModelRegistry(registry_file=reg_path, model_dir=prod_dir)
    loaded = registry.load_active_model_and_preprocessor("recommendation_model")

    db_healthy = True
    try:
        db.session.execute(db.text("SELECT 1"))
    except Exception:
        db_healthy = False

    ml_healthy = loaded.get("status") in ["HEALTHY", "WARNING"]

    status = {
        "status": "healthy" if (db_healthy and ml_healthy) else "degraded",
        "database": "healthy" if db_healthy else "failed",
        "ml_model": "healthy" if ml_healthy else "degraded",
        "fallback_engine": "standby" if ml_healthy else "active",
    }

    return render_template("admin/system_health.html", status=status)


@admin_bp.route("/retrain", methods=["POST"])
@admin_required
def retrain():
    base_dir = current_app.config["BASE_DIR"]
    data_dir = current_app.config["DATA_DIR"]
    model_dir = base_dir / "models"
    reg_path = current_app.config["REGISTRY_PATH"]

    try:
        from app.ml.train_all import run_full_training_pipeline
        run_full_training_pipeline(
            data_dir=data_dir,
            model_dir=model_dir,
            registry_file=reg_path,
            num_samples=10000,
            force_data_gen=False,
        )
        AuditService.log_event("MODEL_RETRAIN", user_id=g.user.id, details={"status": "success"})
        flash("ML models successfully retrained, validated, and registered!", "success")
    except Exception as e:
        flash(f"Retraining failed: {e}", "danger")

    return redirect(url_for("admin.models"))


@admin_bp.route("/rollback", methods=["POST"])
@admin_required
def rollback():
    reg_path = current_app.config["REGISTRY_PATH"]
    prod_dir = current_app.config["MODEL_DIR"]
    registry = ModelRegistry(registry_file=reg_path, model_dir=prod_dir)

    result = registry.rollback("recommendation_model")
    if result["success"]:
        AuditService.log_event("MODEL_ROLLBACK", user_id=g.user.id, details=result)
        flash(result["message"], "success")
    else:
        flash(result["message"], "danger")

    return redirect(url_for("admin.models"))
