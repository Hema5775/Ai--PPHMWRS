"""
Visual Analytics and Progress Blueprint.
Renders historical telemetry trends, Chart.js visualizations, and multi-week progress analytics.
"""

from datetime import date, timedelta
from flask import Blueprint, render_template, g, request
from app.routes.auth import login_required
from app.models.activity import DailyActivity
from app.models.wellness_score import WellnessScore

progress_bp = Blueprint("progress", __name__)


@progress_bp.route("/progress")
@login_required
def index():
    user = g.user
    days = int(request.args.get("days", 14))
    if days not in [7, 14, 30]:
        days = 14

    start_date = date.today() - timedelta(days=days - 1)

    activities = DailyActivity.query.filter(
        DailyActivity.user_id == user.id,
        DailyActivity.date >= start_date,
    ).order_by(DailyActivity.date.asc()).all()

    scores = WellnessScore.query.filter(
        WellnessScore.user_id == user.id,
        WellnessScore.date >= start_date,
    ).order_by(WellnessScore.date.asc()).all()

    score_map = {s.date.isoformat(): s.total_score for s in scores}

    # Prepare contiguous time series data for Chart.js
    labels = []
    steps_data = []
    water_data = []
    sleep_data = []
    exercise_data = []
    score_data = []

    act_map = {a.date.isoformat(): a for a in activities}

    curr = start_date
    while curr <= date.today():
        d_str = curr.isoformat()
        labels.append(curr.strftime("%b %d"))
        act = act_map.get(d_str)
        if act:
            steps_data.append(act.steps)
            water_data.append(round(act.water_liters, 2))
            sleep_data.append(round(act.sleep_hours, 1))
            exercise_data.append(act.exercise_minutes)
        else:
            steps_data.append(0)
            water_data.append(0.0)
            sleep_data.append(0.0)
            exercise_data.append(0)

        score_data.append(score_map.get(d_str, 0.0))
        curr += timedelta(days=1)

    chart_payload = {
        "labels": labels,
        "steps": steps_data,
        "water": water_data,
        "sleep": sleep_data,
        "exercise": exercise_data,
        "scores": score_data,
    }

    has_data = len(activities) > 0

    return render_template(
        "progress.html",
        user=user,
        days=days,
        chart_payload=chart_payload,
        profile=user.profile,
        has_data=has_data,
        logged_days_count=len(activities),
    )
