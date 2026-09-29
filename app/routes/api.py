"""
RESTful API Blueprint.
Provides clean JSON APIs for mobile/client integrations, external consumers, and health monitoring.
"""

from datetime import date, datetime
from flask import Blueprint, request, jsonify, g, session, current_app
from app.extensions import db
from app.models.user import User
from app.models.health_profile import HealthProfile
from app.models.activity import DailyActivity
from app.models.task import DailyTask
from app.models.wellness_score import WellnessScore
from app.models.weekly_report import WeeklyReport
from app.services.scoring_service import ScoringService
from app.services.recommendation_service import RecommendationService
from app.services.activity_service import ActivityService
from app.services.report_service import ReportService
from app.ml.model_registry import ModelRegistry
from app.ml.model_health import ModelHealthMonitor
from app.validation.schemas import (
    UserRegisterSchema,
    UserLoginSchema,
    ProfileUpdateSchema,
    DailyActivitySchema,
    TaskCompleteSchema,
)
from app.validation.validators import format_pydantic_errors
from pydantic import ValidationError

api_bp = Blueprint("api", __name__, url_prefix="/api")


def api_auth_required(f):
    def wrapper(*args, **kwargs):
        if "user_id" not in session:
            return jsonify({"error": "Unauthorized", "message": "Authentication required"}), 401
        return f(*args, **kwargs)
    wrapper.__name__ = f.__name__
    return wrapper


@api_bp.route("/health", methods=["GET"])
def health_check():
    """Application health endpoint per Section 39 specification."""
    db_status = "healthy"
    try:
        db.session.execute(db.text("SELECT 1"))
    except Exception:
        db_status = "failed"

    ml_status = "healthy"
    fallback_active = "standby"
    try:
        reg_path = current_app.config["REGISTRY_PATH"]
        prod_dir = current_app.config["MODEL_DIR"]
        reg = ModelRegistry(registry_file=reg_path, model_dir=prod_dir)
        loaded = reg.load_active_model_and_preprocessor("recommendation_model")
        if loaded.get("status") not in ["HEALTHY", "WARNING"]:
            ml_status = "failed"
            fallback_active = "active"
    except Exception:
        ml_status = "failed"
        fallback_active = "active"

    overall = "healthy" if (db_status == "healthy" and ml_status == "healthy") else "degraded"

    return jsonify({
        "status": overall,
        "database": db_status,
        "ml_model": ml_status,
        "recommendation_engine": "healthy",
        "fallback": fallback_active,
        "timestamp": datetime.utcnow().isoformat(),
    }), (200 if overall == "healthy" else 200)


@api_bp.route("/auth/register", methods=["POST"])
def api_register():
    data = request.get_json(silent=True) or {}
    try:
        validated = UserRegisterSchema(**data)
    except ValidationError as err:
        return jsonify({"error": "ValidationError", "details": format_pydantic_errors(err)}), 422

    if User.query.filter_by(email=validated.email).first():
        return jsonify({"error": "Conflict", "message": "Email already registered"}), 409

    user = User(name=validated.name, email=validated.email, role="user")
    user.set_password(validated.password)
    db.session.add(user)
    db.session.flush()

    profile = HealthProfile(
        user_id=user.id,
        age=validated.age,
        gender=validated.gender,
        height_cm=validated.height_cm,
        weight_kg=validated.weight_kg,
        activity_level=validated.activity_level,
        dietary_preference=validated.dietary_preference,
        health_goal=validated.health_goal,
        allergies=validated.allergies or "",
        physical_limitations=validated.physical_limitations or "none",
    )
    profile.calculate_metrics()
    db.session.add(profile)
    db.session.commit()

    session["user_id"] = user.id
    return jsonify({"message": "Registration successful", "user": user.to_dict()}), 201


@api_bp.route("/auth/login", methods=["POST"])
def api_login():
    data = request.get_json(silent=True) or {}
    try:
        validated = UserLoginSchema(**data)
    except ValidationError as err:
        return jsonify({"error": "ValidationError", "details": format_pydantic_errors(err)}), 422

    user = User.query.filter_by(email=validated.email).first()
    if not user or not user.check_password(validated.password):
        return jsonify({"error": "Unauthorized", "message": "Invalid credentials"}), 401

    session["user_id"] = user.id
    return jsonify({"message": "Login successful", "user": user.to_dict()}), 200


@api_bp.route("/auth/logout", methods=["POST"])
def api_logout():
    session.pop("user_id", None)
    return jsonify({"message": "Logged out successfully"}), 200


@api_bp.route("/profile", methods=["GET"])
@api_auth_required
def api_get_profile():
    user = User.query.get(session["user_id"])
    return jsonify({
        "user": user.to_dict(),
        "profile": user.profile.to_dict() if user.profile else None,
    })


@api_bp.route("/dashboard", methods=["GET"])
@api_auth_required
def api_dashboard():
    user_id = session["user_id"]
    today = date.today()
    score = ScoringService.calculate_daily_wellness_score(user_id=user_id, target_date=today)
    rec = RecommendationService.generate_daily_recommendation(user_id=user_id, target_date=today)
    activity = DailyActivity.query.filter_by(user_id=user_id, date=today).first()
    tasks = DailyTask.query.filter_by(user_id=user_id, date=today).all()

    return jsonify({
        "today": today.isoformat(),
        "wellness_score": score.to_dict() if score else None,
        "recommendation": rec.to_dict() if rec else None,
        "today_activity": activity.to_dict() if activity else None,
        "tasks": [t.to_dict() for t in tasks],
    })


@api_bp.route("/activity", methods=["POST", "GET"])
@api_auth_required
def api_activity():
    user_id = session["user_id"]
    if request.method == "POST":
        data = request.get_json(silent=True) or {}
        try:
            validated = DailyActivitySchema(**data)
        except ValidationError as err:
            return jsonify({"error": "ValidationError", "details": format_pydantic_errors(err)}), 422

        entry_date = validated.date or date.today()
        act = ActivityService.log_daily_activity(
            user_id=user_id,
            entry_date=entry_date,
            steps=validated.steps,
            water_liters=validated.water_liters,
            sleep_hours=validated.sleep_hours,
            exercise_minutes=validated.exercise_minutes,
            exercise_type=validated.exercise_type or "walking",
            sleep_quality=validated.sleep_quality or 3,
            calories_burned=validated.calories_burned,
            mood=validated.mood or "neutral",
            notes=validated.notes,
        )
        return jsonify({"message": "Activity recorded", "activity": act.to_dict()}), 201

    activities = DailyActivity.query.filter_by(user_id=user_id).order_by(DailyActivity.date.desc()).limit(30).all()
    return jsonify([a.to_dict() for a in activities])


@api_bp.route("/recommendations", methods=["GET"])
@api_auth_required
def api_recommendations():
    user_id = session["user_id"]
    rec = RecommendationService.generate_daily_recommendation(user_id=user_id, target_date=date.today())
    return jsonify(rec.to_dict())


@api_bp.route("/wellness-score", methods=["GET"])
@api_auth_required
def api_wellness_score():
    user_id = session["user_id"]
    score = ScoringService.calculate_daily_wellness_score(user_id=user_id, target_date=date.today())
    return jsonify(score.to_dict())


@api_bp.route("/progress", methods=["GET"])
@api_auth_required
def api_progress():
    user_id = session["user_id"]
    activities = ActivityService.get_recent_activities(user_id=user_id, days=30)
    scores = WellnessScore.query.filter_by(user_id=user_id).order_by(WellnessScore.date.desc()).limit(30).all()
    return jsonify({
        "activities": [a.to_dict() for a in activities],
        "scores": [s.to_dict() for s in scores],
    })


@api_bp.route("/weekly-report", methods=["GET"])
@api_auth_required
def api_weekly_report():
    user_id = session["user_id"]
    report = ReportService.generate_weekly_report(user_id=user_id, week_end_date=date.today())
    return jsonify(report.to_dict())


@api_bp.route("/tasks/<int:task_id>/complete", methods=["POST"])
@api_auth_required
def api_complete_task(task_id: int):
    user_id = session["user_id"]
    task = DailyTask.query.filter_by(id=task_id, user_id=user_id).first()
    if not task:
        return jsonify({"error": "NotFound", "message": "Task not found"}), 404

    data = request.get_json(silent=True) or {}
    try:
        val = TaskCompleteSchema(**data)
        status = val.completed
        notes = val.notes
    except ValidationError:
        status = True
        notes = None

    task.mark_completed(status=status, notes=notes)
    db.session.commit()
    ScoringService.calculate_daily_wellness_score(user_id=user_id, target_date=task.date, persist=True)
    return jsonify({"message": "Task status updated", "task": task.to_dict()})


@api_bp.route("/assistant/chat", methods=["POST"])
@api_auth_required
def api_assistant_chat():
    from app.services.assistant_service import WellnessAssistantService
    from app.validation.schemas import AssistantQuerySchema
    data = request.get_json(silent=True) or {}
    try:
        validated = AssistantQuerySchema(**data)
    except ValidationError:
        return jsonify({"reply": "Please enter a valid message.", "disclaimer": WellnessAssistantService.MEDICAL_DISCLAIMER}), 400
    res = WellnessAssistantService.answer_query(user_id=session["user_id"], user_message=validated.message)
    return jsonify(res)


@api_bp.route("/model/status", methods=["GET"])
def api_model_status():
    reg_path = current_app.config["REGISTRY_PATH"]
    prod_dir = current_app.config["MODEL_DIR"]
    reg = ModelRegistry(registry_file=reg_path, model_dir=prod_dir)
    loaded = reg.load_active_model_and_preprocessor("recommendation_model")
    meta = reg.get_active_model_meta("recommendation_model")
    return jsonify({
        "status": loaded.get("status", "UNKNOWN"),
        "meta": meta,
    })


@api_bp.route("/admin/model-health", methods=["GET"])
def api_admin_model_health():
    reg_path = current_app.config["REGISTRY_PATH"]
    prod_dir = current_app.config["MODEL_DIR"]
    reg = ModelRegistry(registry_file=reg_path, model_dir=prod_dir)
    loaded = reg.load_active_model_and_preprocessor("recommendation_model")
    meta = reg.get_active_model_meta("recommendation_model")
    report = ModelHealthMonitor.run_health_checks(
        model_name="recommendation_model",
        model_artifact=loaded.get("model"),
        preprocessor_artifact=loaded.get("preprocessor"),
        meta=meta,
    )
    return jsonify(report)
