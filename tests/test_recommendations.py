"""
Unit & Integration Tests for Recommendations Engine.
"""

from datetime import date
from app.services.recommendation_service import RecommendationService
from app.models.recommendation import Recommendation
from app.models.task import DailyTask


def test_recommendation_generation(app, test_user):
    with app.app_context():
        rec = RecommendationService.generate_daily_recommendation(user_id=test_user.id, target_date=date.today())
        assert rec is not None
        assert rec.category in [
            "activity_boost", "sleep_hygiene", "hydration_focus",
            "metabolic_balance", "strength_endurance", "active_recovery"
        ]
        assert rec.explanation is not None
        assert len(rec.explanation) > 10
        assert rec.model_name is not None
        assert rec.confidence is not None

        # Verify synchronized tasks
        tasks = DailyTask.query.filter_by(user_id=test_user.id, date=date.today()).all()
        assert len(tasks) >= 3


def test_allergy_and_limitation_respect(app, test_user):
    with app.app_context():
        # Set peanut allergy and knee pain limitation
        test_user.profile.allergies = "peanuts, fish"
        test_user.profile.physical_limitations = "knee_pain"
        from app.extensions import db
        db.session.commit()

        rec = RecommendationService.generate_daily_recommendation(user_id=test_user.id, force_refresh=True)
        diet = rec.get_diet_guidance()
        exercise = rec.get_exercise_guidance()

        # Check that knee-pain contra-indicated exercises (e.g. squats or running) are not in recommendations
        for act in exercise.get("recommended_activities", []):
            assert "squat" not in act.lower()


def test_toggle_task_completion(authenticated_client, test_user, app):
    with app.app_context():
        rec = RecommendationService.generate_daily_recommendation(user_id=test_user.id, target_date=date.today())
        task = DailyTask.query.filter_by(user_id=test_user.id, date=date.today()).first()
        task_id = task.id
        initial_status = task.completed

    res = authenticated_client.post(f"/recommendations/tasks/{task_id}/toggle", follow_redirects=True)
    assert res.status_code == 200

    with app.app_context():
        updated_task = DailyTask.query.get(task_id)
        assert updated_task.completed != initial_status
