"""
RESTful API Integration Tests.
"""

from datetime import date
from app.services.recommendation_service import RecommendationService
from app.models.task import DailyTask


def test_api_health_check(client):
    res = client.get("/api/health")
    assert res.status_code == 200
    data = res.get_json()
    assert data["status"] in ["healthy", "degraded"]
    assert "database" in data
    assert "ml_model" in data


def test_api_dashboard_and_recommendations(authenticated_client, test_user, app):
    # Dashboard API
    res_dash = authenticated_client.get("/api/dashboard")
    assert res_dash.status_code == 200
    dash_data = res_dash.get_json()
    assert "wellness_score" in dash_data
    assert "recommendation" in dash_data

    # Recommendations API
    res_rec = authenticated_client.get("/api/recommendations")
    assert res_rec.status_code == 200
    rec_data = res_rec.get_json()
    assert "category" in rec_data
    assert "explanation" in rec_data


def test_api_log_activity(authenticated_client, test_user, app):
    payload = {
        "date": date.today().isoformat(),
        "steps": 9200,
        "water_liters": 2.6,
        "sleep_hours": 7.8,
        "exercise_minutes": 40,
        "exercise_type": "cycling",
        "sleep_quality": 4,
        "calories_burned": 2350,
        "mood": "great",
        "notes": "API test logged entry",
    }
    res = authenticated_client.post("/api/activity", json=payload)
    assert res.status_code == 201
    data = res.get_json()
    assert data["activity"]["steps"] == 9200


def test_api_complete_task(authenticated_client, test_user, app):
    with app.app_context():
        RecommendationService.generate_daily_recommendation(user_id=test_user.id, target_date=date.today())
        task = DailyTask.query.filter_by(user_id=test_user.id, date=date.today()).first()
        task_id = task.id

    res = authenticated_client.post(f"/api/tasks/{task_id}/complete", json={"completed": True, "notes": "Done via API"})
    assert res.status_code == 200
    data = res.get_json()
    assert data["task"]["completed"] is True
