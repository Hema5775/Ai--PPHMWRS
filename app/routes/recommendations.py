"""
Personalized Recommendations Blueprint.
Renders daily diet, exercise, hydration, and task guidance with full explainability and model provenance.
"""

from datetime import date
from flask import Blueprint, render_template, redirect, url_for, flash, g, request
from app.routes.auth import login_required
from app.models.task import DailyTask
from app.services.recommendation_service import RecommendationService
from app.services.scoring_service import ScoringService

recommendations_bp = Blueprint("recommendations", __name__)


@recommendations_bp.route("/recommendations")
@login_required
def index():
    user = g.user
    today = date.today()

    rec = RecommendationService.generate_daily_recommendation(user_id=user.id, target_date=today)
    tasks = DailyTask.query.filter_by(user_id=user.id, date=today).order_by(DailyTask.id.asc()).all()

    return render_template(
        "recommendations.html",
        user=user,
        today=today,
        recommendation=rec,
        tasks=tasks,
    )


@recommendations_bp.route("/recommendations/refresh", methods=["POST"])
@login_required
def refresh():
    user = g.user
    today = date.today()
    try:
        RecommendationService.generate_daily_recommendation(user_id=user.id, target_date=today, force_refresh=True)
        flash("Recommendations re-evaluated against your latest profile and activities.", "success")
    except Exception as e:
        flash(f"Could not refresh recommendations: {e}", "danger")
    return redirect(url_for("recommendations.index"))


@recommendations_bp.route("/recommendations/tasks/<int:task_id>/toggle", methods=["POST"])
@login_required
def toggle_task(task_id: int):
    user = g.user
    task = DailyTask.query.filter_by(id=task_id, user_id=user.id).first_or_404()
    task.mark_completed(not task.completed)
    from app.extensions import db
    db.session.commit()

    # Recalculate wellness score for the task date
    ScoringService.calculate_daily_wellness_score(user_id=user.id, target_date=task.date, persist=True)

    status_str = "completed" if task.completed else "pending"
    flash(f"Task '{task.title}' marked as {status_str}.", "info")
    return redirect(request.referrer or url_for("recommendations.index"))
