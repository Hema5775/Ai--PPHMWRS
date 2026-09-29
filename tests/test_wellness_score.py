"""
Unit Tests for Model B — Transparent Wellness Score Engine.
"""

from datetime import date
from app.services.scoring_service import ScoringService
from app.services.activity_service import ActivityService


def test_wellness_score_bounds_and_weights(app, test_user):
    with app.app_context():
        today = date.today()
        # Log good activity
        ActivityService.log_daily_activity(
            user_id=test_user.id,
            entry_date=today,
            steps=8500,
            water_liters=2.5,
            sleep_hours=8.0,
            exercise_minutes=45,
            sleep_quality=5,
        )

        score = ScoringService.calculate_daily_wellness_score(user_id=test_user.id, target_date=today, persist=True)

        assert score is not None
        assert 0.0 <= score.total_score <= 100.0
        assert 0.0 <= score.activity_score <= 100.0
        assert 0.0 <= score.hydration_score <= 100.0
        assert 0.0 <= score.sleep_score <= 100.0
        assert 0.0 <= score.task_score <= 100.0
        assert 0.0 <= score.consistency_score <= 100.0

        # Formula string should be populated
        assert "Wellness Score =" in score.calculation_formula
        assert "Activity" in score.calculation_formula
        assert "Hydration" in score.calculation_formula


def test_wellness_score_zero_activity(app, test_user):
    with app.app_context():
        future_date = date(2030, 1, 1)
        score = ScoringService.calculate_daily_wellness_score(user_id=test_user.id, target_date=future_date, persist=False)
        assert score.activity_score == 0.0
        assert score.hydration_score == 0.0
        assert 0.0 <= score.total_score <= 100.0
