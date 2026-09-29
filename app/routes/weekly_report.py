"""
Weekly Report Blueprint.
Compiles and displays deep-dive weekly progress reports with achievements, focus areas, and trends.
"""

from datetime import date
from flask import Blueprint, render_template, g, request
from app.routes.auth import login_required
from app.services.report_service import ReportService
from app.models.weekly_report import WeeklyReport

weekly_report_bp = Blueprint("weekly_report", __name__)


@weekly_report_bp.route("/weekly-report")
@login_required
def index():
    user = g.user
    today = date.today()

    # Generate or get current weekly report
    report = ReportService.generate_weekly_report(user_id=user.id, week_end_date=today)

    # Fetch past reports
    past_reports = WeeklyReport.query.filter(
        WeeklyReport.user_id == user.id,
        WeeklyReport.id != report.id,
    ).order_by(WeeklyReport.week_start.desc()).limit(10).all()

    from app.models.activity import DailyActivity

    # Count actual days logged in this 7-day period
    logged_days_count = DailyActivity.query.filter(
        DailyActivity.user_id == user.id,
        DailyActivity.date >= report.week_start,
        DailyActivity.date <= report.week_end,
    ).count()

    return render_template(
        "weekly_report.html",
        user=user,
        report=report,
        past_reports=past_reports,
        profile=user.profile,
        logged_days_count=logged_days_count,
    )
