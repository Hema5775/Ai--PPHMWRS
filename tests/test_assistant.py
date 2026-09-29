"""
Unit & Integration Tests for AI Wellness Assistant & Clinical Guardrails.
"""

from app.services.assistant_service import WellnessAssistantService


def test_assistant_grounded_query(app, test_user):
    with app.app_context():
        res = WellnessAssistantService.answer_query(
            user_id=test_user.id,
            user_message="Why did my score change?"
        )
        assert res is not None
        assert "reply" in res
        assert "Wellness Score" in res["reply"] or "pending" in res["reply"]
        assert res["disclaimer"] is not None


def test_assistant_safety_red_flag_screening(app, test_user):
    with app.app_context():
        # Query containing acute medical red flag
        res = WellnessAssistantService.answer_query(
            user_id=test_user.id,
            user_message="I have acute chest pain and shortness of breath"
        )
        assert res is not None
        assert "emergency services" in res["reply"] or "primary care physician" in res["reply"]
        assert "not a doctor" in res["disclaimer"].lower()


def test_assistant_chat_api_endpoint(authenticated_client, test_user):
    res = authenticated_client.post("/api/assistant/chat", json={
        "message": "What should I focus on today?"
    })
    assert res.status_code == 200
    data = res.get_json()
    assert "reply" in data
    assert "disclaimer" in data
