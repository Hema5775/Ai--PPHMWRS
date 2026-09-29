"""
Unit & Integration Tests for Authentication.
"""

from app.models.user import User


def test_user_password_hashing(app):
    user = User(name="Secure User", email="secure@wellness.ai")
    user.set_password("MyStrongPass123!")
    assert user.password_hash != "MyStrongPass123!"
    assert user.check_password("MyStrongPass123!")
    assert not user.check_password("WrongPassword")


def test_registration_flow(client, app):
    res = client.post("/register", data={
        "name": "New Registered User",
        "email": "newuser@wellness.ai",
        "password": "Password123!",
        "age": 29,
        "gender": "male",
        "height_cm": 178.0,
        "weight_kg": 75.0,
        "activity_level": "moderately_active",
        "dietary_preference": "mediterranean",
        "health_goal": "weight_loss",
        "physical_limitations": "none",
        "allergies": "",
    }, follow_redirects=True)

    assert res.status_code == 200
    assert b"Welcome to your AI Wellness Companion" in res.data or b"Dashboard" in res.data

    with app.app_context():
        user = User.query.filter_by(email="newuser@wellness.ai").first()
        assert user is not None
        assert user.profile is not None
        assert user.profile.bmi is not None
        assert user.profile.bmr is not None


def test_login_and_logout(client, test_user):
    # Successful login
    res = client.post("/login", data={
        "email": "test@wellness.ai",
        "password": "TestSecret123!"
    }, follow_redirects=True)
    assert res.status_code == 200
    assert b"Welcome back" in res.data

    # Logout
    res_logout = client.get("/logout", follow_redirects=True)
    assert res_logout.status_code == 200
    assert b"logged out" in res_logout.data


def test_login_invalid_credentials(client, test_user):
    res = client.post("/login", data={
        "email": "test@wellness.ai",
        "password": "WrongPassword!"
    }, follow_redirects=True)
    assert res.status_code == 200
    assert b"Invalid email or password" in res.data
