"""
Integration Tests for Progress Analytics and Weekly Reports.
"""

from datetime import date
from app.services.activity_service import ActivityService
from app.services.report_service import ReportService


def test_progress_page(authenticated_client, test_user, app):
    # Log some activities
    with app.app_context():
        ActivityService.log_daily_activity(
            user_id=test_user.id,
            entry_date=date.today(),
            steps=7500,
            water_liters=2.4,
            sleep_hours=7.2,
            exercise_minutes=30,
        )

    res = authenticated_client.get("/progress?days=7")
    assert res.status_code == 200
    assert b"Visual Analytics" in res.data
    assert b"progressStepsChart" in res.data


def test_weekly_report_page(authenticated_client, test_user, app):
    with app.app_context():
        ReportService.generate_weekly_report(user_id=test_user.id, week_end_date=date.today())

    res = authenticated_client.get("/weekly-report")
    assert res.status_code == 200
    assert b"Weekly Behavioral & Wellness Report" in res.data
    assert b"Longitudinal Trend Assessment" in res.data
