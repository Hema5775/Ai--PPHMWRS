"""
Unit & Integration Tests for Daily Activity Tracking & Anomaly Detection (Model D).
"""

from datetime import date
from app.services.activity_service import ActivityService
from app.models.activity import DailyActivity


def test_log_normal_activity(app, test_user):
    with app.app_context():
        today = date.today()
        act = ActivityService.log_daily_activity(
            user_id=test_user.id,
            entry_date=today,
            steps=8500,
            water_liters=2.5,
            sleep_hours=7.5,
            exercise_minutes=35,
            exercise_type="walking",
        )
        assert act.id is not None
        assert act.steps == 8500
        assert act.water_liters == 2.5
        assert not act.is_anomaly


def test_anomaly_detection_extreme_entry(app, test_user):
    with app.app_context():
        today = date.today()
        # Extreme values that should trigger data quality anomaly
        act = ActivityService.log_daily_activity(
            user_id=test_user.id,
            entry_date=today,
            steps=55000,
            water_liters=0.1,
            sleep_hours=1.0,
            exercise_minutes=300,
        )
        assert act.is_anomaly
        assert act.anomaly_reason is not None


def test_activity_post_route(authenticated_client, test_user, app):
    res = authenticated_client.post("/activity", data={
        "date": date.today().isoformat(),
        "steps": 7200,
        "water_liters": 2.2,
        "sleep_hours": 7.0,
        "sleep_quality": 4,
        "exercise_minutes": 25,
        "exercise_type": "running",
        "calories_burned": 2200,
        "mood": "great",
        "notes": "Felt good after run",
    }, follow_redirects=True)

    assert res.status_code == 200
    with app.app_context():
        act = DailyActivity.query.filter_by(user_id=test_user.id, date=date.today()).first()
        assert act is not None
        assert act.steps == 7200
        assert act.mood == "great"
