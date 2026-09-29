"""
Regression test suite executing the exact user journeys specified in Section 26:
A. Existing email/password user: login -> dashboard -> activity -> save activity -> logout -> login again -> data remains
B. New Google user: Google login -> new local user -> onboarding -> profile -> dashboard -> activity -> logout -> Google login again -> same local user -> data remains
C. New Apple user: Apple login -> new local user -> onboarding -> dashboard -> activity -> logout -> Apple login again -> same local user -> data remains
D. Existing user with matching verified email: Google/Apple login -> safe account resolution -> no accidental duplicate account
"""

import time
import json
from datetime import date
from unittest.mock import patch
import jwt

from app.extensions import db
from app.models.user import User
from app.models.health_profile import HealthProfile
from app.models.activity import DailyActivity


def test_regression_sequence_a_email_password_user(client, app):
    """
    Scenario A: Existing email/password user
    login -> dashboard -> activity -> save activity -> logout -> login again -> data remains
    """
    # Setup user
    with app.app_context():
        user = User(name="Scenario A User", email="scenario_a@wellness.ai", role="user")
        user.set_password("ScenarioAPass123!")
        db.session.add(user)
        db.session.flush()

        profile = HealthProfile(
            user_id=user.id,
            age=30,
            gender="male",
            height_cm=180.0,
            weight_kg=78.0,
            activity_level="moderately_active",
            dietary_preference="balanced",
            health_goal="maintenance",
        )
        profile.calculate_metrics()
        db.session.add(profile)
        db.session.commit()
        user_id = user.id

    # 1. Login
    res_login = client.post(
        "/login",
        data={"email": "scenario_a@wellness.ai", "password": "ScenarioAPass123!"},
        follow_redirects=True,
    )
    assert res_login.status_code == 200
    assert b"Welcome back, Scenario A User!" in res_login.data

    # 2. Activity page
    res_act = client.get("/activity")
    assert res_act.status_code == 200

    # 3. Save activity
    today_str = date.today().isoformat()
    res_save = client.post(
        "/activity",
        data={
            "date": today_str,
            "steps": 10500,
            "distance_km": 7.5,
            "calories_burned": 520,
            "active_minutes": 60,
            "water_liters": 2.8,
            "sleep_hours": 7.8,
            "sleep_quality": 4,
            "mood": "great",
            "stress_level": 2,
        },
        follow_redirects=True,
    )
    assert res_save.status_code == 200
    assert b"activity has been saved" in res_save.data

    # 4. Logout
    res_logout = client.get("/logout", follow_redirects=True)
    assert res_logout.status_code == 200
    assert b"logged out" in res_logout.data

    # 5. Login again
    res_relogin = client.post(
        "/login",
        data={"email": "scenario_a@wellness.ai", "password": "ScenarioAPass123!"},
        follow_redirects=True,
    )
    assert res_relogin.status_code == 200

    # 6. Verify data remains
    with app.app_context():
        saved_activity = DailyActivity.query.filter_by(user_id=user_id, date=date.today()).first()
        assert saved_activity is not None
        assert saved_activity.steps == 10500
        assert saved_activity.water_liters == 2.8


def test_regression_sequence_b_new_google_user(client, app):
    """
    Scenario B: New Google user
    Google login -> new local user -> onboarding -> profile -> dashboard -> activity -> logout -> Google login again -> same local user -> data remains
    """
    app.config["GOOGLE_CLIENT_ID"] = "mock-id"
    app.config["GOOGLE_CLIENT_SECRET"] = "mock-secret"

    mock_google_info = {
        "sub": "google-scenario-b-sub-123",
        "email": "scenario_b@gmail.com",
        "name": "Scenario B Google User",
        "email_verified": True,
    }

    # 1. First Google Login: redirects to /onboarding
    with client.session_transaction() as sess:
        sess["google_oauth_state"] = "state-google-b1"

    with patch("app.routes.auth._exchange_google_code", return_value={"access_token": "mock-token"}), \
         patch("app.routes.auth._fetch_google_userinfo", return_value=mock_google_info):
        res_g1 = client.get("/auth/google/callback?code=code-b1&state=state-google-b1", follow_redirects=False)

    assert res_g1.status_code == 302
    assert "/onboarding" in res_g1.headers["Location"]

    # 2. Complete onboarding
    res_onboard = client.post(
        "/onboarding",
        data={
            "age": 27,
            "gender": "female",
            "height_cm": 165.0,
            "weight_kg": 58.0,
            "activity_level": "moderately_active",
            "dietary_preference": "balanced",
            "health_goal": "weight_loss",
            "allergies": "",
            "physical_limitations": "none",
        },
        follow_redirects=True,
    )
    assert res_onboard.status_code == 200
    assert b"Welcome to Vitalis AI" in res_onboard.data or b"Dashboard" in res_onboard.data

    # 3. Log activity
    res_act = client.post(
        "/activity",
        data={
            "date": date.today().isoformat(),
            "steps": 9200,
            "distance_km": 6.2,
            "calories_burned": 440,
            "active_minutes": 45,
            "water_liters": 2.5,
            "sleep_hours": 8.0,
            "sleep_quality": 4,
            "mood": "good",
            "stress_level": 3,
        },
        follow_redirects=True,
    )
    assert res_act.status_code == 200

    # 4. Logout
    client.get("/logout", follow_redirects=True)

    # 5. Google Login again: should direct straight to /dashboard (no onboarding needed)
    with client.session_transaction() as sess:
        sess["google_oauth_state"] = "state-google-b2"

    with patch("app.routes.auth._exchange_google_code", return_value={"access_token": "mock-token"}), \
         patch("app.routes.auth._fetch_google_userinfo", return_value=mock_google_info):
        res_g2 = client.get("/auth/google/callback?code=code-b2&state=state-google-b2", follow_redirects=False)

    assert res_g2.status_code == 302
    assert "/dashboard" in res_g2.headers["Location"]

    # 6. Data remains & same local user confirmed
    with app.app_context():
        user = User.query.filter_by(google_id="google-scenario-b-sub-123").first()
        assert user is not None
        assert user.email == "scenario_b@gmail.com"
        activity = DailyActivity.query.filter_by(user_id=user.id, date=date.today()).first()
        assert activity is not None
        assert activity.steps == 9200


def test_regression_sequence_c_new_apple_user(client, app):
    """
    Scenario C: New Apple user
    Apple login -> new local user -> onboarding -> dashboard -> activity -> logout -> Apple login again -> same local user -> data remains
    """
    app.config["APPLE_CLIENT_ID"] = "com.vitalis.wellness.service"

    mock_token = jwt.encode(
        {
            "sub": "apple-scenario-c-sub-456",
            "email": "scenario_c@privaterelay.appleid.com",
            "iss": "https://appleid.apple.com",
            "aud": "com.vitalis.wellness.service",
            "exp": int(time.time()) + 3600,
        },
        "test-secret-key-for-testing-32chars!",
        algorithm="HS256",
    )

    # 1. First Apple Login: creates user, redirects to /onboarding
    with client.session_transaction() as sess:
        sess["apple_oauth_state"] = "state-apple-c1"

    user_payload = json.dumps({"name": {"firstName": "Carlos", "lastName": "Apple"}})
    res_a1 = client.post(
        "/auth/apple/callback",
        data={
            "id_token": mock_token,
            "state": "state-apple-c1",
            "user": user_payload,
        },
        follow_redirects=False,
    )
    assert res_a1.status_code == 302
    assert "/onboarding" in res_a1.headers["Location"]

    # 2. Complete onboarding
    res_onboard = client.post(
        "/onboarding",
        data={
            "age": 31,
            "gender": "male",
            "height_cm": 174.0,
            "weight_kg": 70.0,
            "activity_level": "moderately_active",
            "dietary_preference": "balanced",
            "health_goal": "muscle_gain",
            "allergies": "",
            "physical_limitations": "none",
        },
        follow_redirects=True,
    )
    assert res_onboard.status_code == 200

    # 3. Log activity
    res_act = client.post(
        "/activity",
        data={
            "date": date.today().isoformat(),
            "steps": 11200,
            "distance_km": 8.0,
            "calories_burned": 610,
            "active_minutes": 65,
            "water_liters": 3.0,
            "sleep_hours": 7.5,
            "sleep_quality": 5,
            "mood": "great",
            "stress_level": 2,
        },
        follow_redirects=True,
    )
    assert res_act.status_code == 200

    # 4. Logout
    client.get("/logout", follow_redirects=True)

    # 5. Apple login again: should go directly to /dashboard
    with client.session_transaction() as sess:
        sess["apple_oauth_state"] = "state-apple-c2"

    res_a2 = client.post(
        "/auth/apple/callback",
        data={"id_token": mock_token, "state": "state-apple-c2"},
        follow_redirects=False,
    )
    assert res_a2.status_code == 302
    assert "/dashboard" in res_a2.headers["Location"]

    # 6. Verify same local user and persisted activity
    with app.app_context():
        user = User.query.filter_by(apple_id="apple-scenario-c-sub-456").first()
        assert user is not None
        assert user.name == "Carlos Apple"
        activity = DailyActivity.query.filter_by(user_id=user.id, date=date.today()).first()
        assert activity is not None
        assert activity.steps == 11200


def test_regression_sequence_d_existing_user_matching_verified_email(client, app):
    """
    Scenario D: Existing user with matching verified email
    Google/Apple login -> safe account resolution -> no accidental duplicate account
    """
    app.config["GOOGLE_CLIENT_ID"] = "mock-id"
    app.config["GOOGLE_CLIENT_SECRET"] = "mock-secret"
    app.config["APPLE_CLIENT_ID"] = "com.vitalis.wellness.service"

    with app.app_context():
        user = User(
            name="Diana Prince",
            email="diana@themyscira.io",
            auth_provider="local",
        )
        user.set_password("AmazonSecret123!")
        db.session.add(user)
        db.session.flush()

        profile = HealthProfile(
            user_id=user.id,
            age=28,
            gender="female",
            height_cm=178.0,
            weight_kg=68.0,
            activity_level="very_active",
            dietary_preference="mediterranean",
            health_goal="maintenance",
        )
        profile.calculate_metrics()
        db.session.add(profile)
        db.session.commit()
        diana_id = user.id

    # 1. Google login with matching verified email
    with client.session_transaction() as sess:
        sess["google_oauth_state"] = "state-google-d"

    mock_google_info = {
        "sub": "google-diana-sub-789",
        "email": "diana@themyscira.io",
        "name": "Diana Prince",
        "email_verified": True,
    }

    with patch("app.routes.auth._exchange_google_code", return_value={"access_token": "mock-token"}), \
         patch("app.routes.auth._fetch_google_userinfo", return_value=mock_google_info):
        res_g = client.get("/auth/google/callback?code=code-d&state=state-google-d", follow_redirects=False)

    assert res_g.status_code == 302
    assert "/dashboard" in res_g.headers["Location"]

    # Verify no duplicate user, safe link
    with app.app_context():
        matching = User.query.filter_by(email="diana@themyscira.io").all()
        assert len(matching) == 1
        assert matching[0].id == diana_id
        assert matching[0].google_id == "google-diana-sub-789"
        assert "google" in matching[0].auth_provider

    # 2. Apple login with matching verified email
    with client.session_transaction() as sess:
        sess["apple_oauth_state"] = "state-apple-d"

    mock_apple_token = jwt.encode(
        {
            "sub": "apple-diana-sub-999",
            "email": "diana@themyscira.io",
            "iss": "https://appleid.apple.com",
            "aud": "com.vitalis.wellness.service",
            "exp": int(time.time()) + 3600,
        },
        "test-secret-key-for-testing-32chars!",
        algorithm="HS256",
    )

    res_a = client.post(
        "/auth/apple/callback",
        data={"id_token": mock_apple_token, "state": "state-apple-d"},
        follow_redirects=False,
    )

    assert res_a.status_code == 302
    assert "/dashboard" in res_a.headers["Location"]

    # Verify still exactly 1 user record, now linked with both Google and Apple!
    with app.app_context():
        matching = User.query.filter_by(email="diana@themyscira.io").all()
        assert len(matching) == 1
        user_record = matching[0]
        assert user_record.id == diana_id
        assert user_record.google_id == "google-diana-sub-789"
        assert user_record.apple_id == "apple-diana-sub-999"
        assert "google" in user_record.auth_provider
        assert "apple" in user_record.auth_provider
