"""
Daily Activity Tracking Blueprint.
Enables users to log daily activity parameters, review history, and view anomaly alerts.
"""

from datetime import date, datetime
from flask import Blueprint, render_template, request, redirect, url_for, flash, g
from app.extensions import db
from app.routes.auth import login_required
from app.models.activity import DailyActivity
from app.services.activity_service import ActivityService
from app.services.recommendation_service import RecommendationService
from app.services.audit_service import AuditService
from app.validation.schemas import DailyActivitySchema
from app.validation.validators import format_pydantic_errors
from pydantic import ValidationError

activity_bp = Blueprint("activity", __name__)


@activity_bp.route("/activity", methods=["GET", "POST"])
@login_required
def index():
    user = g.user
    today = date.today()

    if request.method == "POST":
        date_str = request.form.get("date")
        try:
            entry_date = datetime.strptime(date_str, "%Y-%m-%d").date() if date_str else today
        except ValueError:
            entry_date = today

        form_data = {
            "date": entry_date,
            "steps": int(request.form.get("steps", 0)) if request.form.get("steps") else 0,
            "water_liters": float(request.form.get("water_liters", 0.0)) if request.form.get("water_liters") else 0.0,
            "sleep_hours": float(request.form.get("sleep_hours", 0.0)) if request.form.get("sleep_hours") else 0.0,
            "sleep_quality": (lambda v: int(v) if str(v).isdigit() else {"poor": 1, "fair": 2, "good": 3, "great": 4, "excellent": 5}.get(str(v).lower(), 3))(request.form.get("sleep_quality", 3)),
            "exercise_minutes": int(request.form.get("exercise_minutes", 0)) if request.form.get("exercise_minutes") else 0,
            "exercise_type": request.form.get("exercise_type", "walking"),
            "calories_burned": float(request.form.get("calories_burned", 0.0)) if request.form.get("calories_burned") else None,
            "mood": request.form.get("mood", "neutral"),
            "notes": request.form.get("notes", "").strip(),
        }

        try:
            validated = DailyActivitySchema(**form_data)
        except ValidationError as err:
            errors = format_pydantic_errors(err)
            for e in errors:
                flash(f"{e['field']}: {e['message']}", "danger")
            return redirect(url_for("activity.index"))

        # Save activity via service (screens anomalies with Model D and recalculates wellness score)
        act = ActivityService.log_daily_activity(
            user_id=user.id,
            entry_date=entry_date,
            steps=validated.steps,
            water_liters=validated.water_liters,
            sleep_hours=validated.sleep_hours,
            exercise_minutes=validated.exercise_minutes,
            exercise_type=validated.exercise_type,
            sleep_quality=validated.sleep_quality,
            calories_burned=validated.calories_burned,
            mood=validated.mood,
            notes=validated.notes,
        )

        AuditService.log_event("ACTIVITY_LOG", user_id=user.id, details={"date": str(entry_date), "steps": act.steps})

        # Update recommendation
        try:
            RecommendationService.generate_daily_recommendation(user_id=user.id, target_date=entry_date, force_refresh=True)
        except Exception:
            pass

        # Update weekly report so progress and reports immediately reflect new activity
        try:
            from app.services.report_service import ReportService
            ReportService.generate_weekly_report(user_id=user.id, week_end_date=max(entry_date, today))
        except Exception:
            pass

        if act.is_anomaly:
            flash(
                f"Today's activity has been saved. Note: Activity Insights flagged an unusual pattern ({act.anomaly_reason}). "
                "Double-check your numbers to ensure data accuracy.",
                "warning"
            )
        else:
            flash("Today's activity has been saved.", "success")

        return redirect(url_for("activity.index"))

    # Fetch today's activity and user longitudinal activity history (newest first)
    today_act = DailyActivity.query.filter_by(user_id=user.id, date=today).first()
    history = DailyActivity.query.filter_by(user_id=user.id).order_by(DailyActivity.date.desc()).all()

    return render_template(
        "activity.html",
        user=user,
        today=today,
        today_activity=today_act,
        history=history,
        profile=user.profile,
    )
