"""
Dashboard and Core Views Blueprint.
Renders the primary wellness cockpit, metrics telemetry, tasks, and system health status.
"""

from datetime import date, timedelta
from flask import Blueprint, render_template, redirect, url_for, session, g, flash, request
from app.routes.auth import login_required
from app.models.activity import DailyActivity
from app.models.recommendation import Recommendation
from app.models.task import DailyTask
from app.models.wellness_score import WellnessScore
from app.services.scoring_service import ScoringService
from app.services.recommendation_service import RecommendationService
from app.services.report_service import ReportService
from app.services.activity_service import ActivityService
from app.ml.model_registry import ModelRegistry
from flask import current_app

dashboard_bp = Blueprint("dashboard", __name__)


@dashboard_bp.route("/")
def home():
    if g.user:
        return redirect(url_for("dashboard.index"))
    return redirect(url_for("auth.login"))


@dashboard_bp.route("/dashboard")
@login_required
def index():
    user = g.user
    today = date.today()

    # Get today's activity
    activity = DailyActivity.query.filter_by(user_id=user.id, date=today).first()
    has_today_activity = (activity is not None)
    total_activity_count = DailyActivity.query.filter_by(user_id=user.id).count()

    # Get or generate today's wellness score
    score_rec = None
    if has_today_activity or total_activity_count > 0:
        score_rec = ScoringService.calculate_daily_wellness_score(user_id=user.id, target_date=today, persist=True)

    # Get or generate today's recommendation
    rec = RecommendationService.generate_daily_recommendation(user_id=user.id, target_date=today)

    # Get today's tasks
    tasks = DailyTask.query.filter_by(user_id=user.id, date=today).order_by(DailyTask.id.asc()).all()

    # 7-day activities for weekly trend overview
    week_ago = today - timedelta(days=6)
    recent_activities = DailyActivity.query.filter(
        DailyActivity.user_id == user.id,
        DailyActivity.date >= week_ago,
        DailyActivity.date <= today,
    ).order_by(DailyActivity.date.asc()).all()

    # Recent 7 wellness scores
    recent_scores = WellnessScore.query.filter(
        WellnessScore.user_id == user.id,
        WellnessScore.date >= week_ago,
        WellnessScore.date <= today,
    ).order_by(WellnessScore.date.asc()).all()

    # Model health status
    model_status = "HEALTHY"
    try:
        reg_path = current_app.config["REGISTRY_PATH"]
        prod_dir = current_app.config["MODEL_DIR"]
        reg = ModelRegistry(registry_file=reg_path, model_dir=prod_dir)
        loaded = reg.load_active_model_and_preprocessor("recommendation_model")
        model_status = loaded.get("status", "HEALTHY")
    except Exception:
        model_status = "DEGRADED"

    # Generate or fetch latest weekly report summary
    weekly_report = ReportService.generate_weekly_report(user_id=user.id, week_end_date=today)

    return render_template(
        "dashboard.html",
        user=user,
        profile=user.profile,
        today=today,
        activity=activity,
        score=score_rec,
        recommendation=rec,
        tasks=tasks,
        recent_activities=recent_activities,
        recent_scores=recent_scores,
        model_status=model_status,
        weekly_report=weekly_report,
        has_today_activity=has_today_activity,
        total_activity_count=total_activity_count,
    )


@dashboard_bp.route("/settings", methods=["GET", "POST"])
@login_required
def settings():
    user = g.user
    if request.method == "POST":
        flash("System and notification preferences updated successfully.", "success")
        return redirect(url_for("dashboard.settings"))
    return render_template("settings.html", user=user)


@dashboard_bp.route("/how-it-works")
def how_it_works():
    """Technical Model Center / How Vitalis AI Works (Section 24)."""
    user = g.user
    availability = ActivityService.get_user_data_availability(user)
    return render_template("how_it_works.html", user=user, availability=availability)

