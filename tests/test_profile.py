"""
Unit & Integration Tests for Health Profile & Deterministic Metrics.
"""

from app.models.health_profile import HealthProfile
from app.extensions import db


def test_deterministic_bmi_and_bmr(app):
    with app.app_context():
        # Male, 180cm, 80kg, age 30
        profile = HealthProfile(
            user_id=999,
            age=30,
            gender="male",
            height_cm=180.0,
            weight_kg=80.0,
        )
        profile.calculate_metrics()
        # BMI = 80 / (1.8^2) = 24.69
        assert profile.bmi == 24.69
        # BMR = (10*80) + (6.25*180) - (5*30) + 5 = 800 + 1125 - 150 + 5 = 1780.0
        assert profile.bmr == 1780.0


def test_profile_update_route(authenticated_client, test_user, app):
    res = authenticated_client.post("/profile", data={
        "name": "Updated Test Name",
        "age": 31,
        "gender": "female",
        "height_cm": 166.0,
        "weight_kg": 59.0,
        "activity_level": "very_active",
        "dietary_preference": "vegetarian",
        "health_goal": "cardio_endurance",
        "physical_limitations": "none",
        "allergies": "dairy",
        "target_steps": 10000,
        "target_water_liters": 2.8,
        "target_sleep_hours": 8.0,
    }, follow_redirects=True)

    assert res.status_code == 200
    with app.app_context():
        prof = HealthProfile.query.filter_by(user_id=test_user.id).first()
        assert prof.age == 31
        assert prof.dietary_preference == "vegetarian"
        assert prof.health_goal == "cardio_endurance"
        assert prof.target_steps == 10000
        assert prof.allergies == "dairy"
