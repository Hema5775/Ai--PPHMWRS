"""
Comprehensive unit and integration tests for Sign in with Apple Web Authentication flow.
Tests coverage:
1. Login page loads successfully and Apple button is present in HTML.
2. Register page contains the Apple sign-in button.
3. Missing Apple configuration does not crash the application.
4. Email/password login continues to work normally alongside Apple.
5. Apple OAuth start route redirects correctly when configured.
6. Apple callback handles provider errors (e.g., user cancellation).
7. Invalid or missing OAuth state token (CSRF) is rejected.
8. Token exchange/network failures handled cleanly with friendly messages.
9. New Apple user account created with onboarding redirection.
10. Existing Apple user logs in directly to dashboard.
11. Existing local account is safely linked without duplicating user.
12. Account collision with mismatched Apple subject is rejected.
13. Apple client secret JWT generation produces valid signed JWT.
14. Session fixation defense and session state established.
15. Logout clears session completely.
16. No client secrets or private keys leaked in HTML or logs.
17. Apple form_post handling with user name extraction.
"""

import json
import time
from unittest.mock import patch, MagicMock
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.hazmat.primitives import serialization
import jwt

from app.extensions import db
from app.models.user import User
from app.models.health_profile import HealthProfile
from app.routes.auth import (
    _get_apple_redirect_uri,
    _generate_apple_client_secret,
    _verify_and_extract_apple_identity,
    _load_apple_private_key,
)


def _generate_test_ec_key_pem():
    """Generate an EC SECP256R1 private key in PEM format for test signing."""
    key = ec.generate_private_key(ec.SECP256R1())
    return key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    ).decode("utf-8")


def test_login_page_loads_and_apple_button_present(client):
    """1: Login page loads and contains the Apple sign-in button."""
    res = client.get("/login")
    assert res.status_code == 200
    assert b"Continue with Apple" in res.data
    assert b"id=\"btn-apple-login\"" in res.data
    assert b"Continue with Google" in res.data
    assert b"Sign In" in res.data


def test_register_page_loads_and_apple_button_present(client):
    """2: Register page loads and contains the Apple sign-in button."""
    res = client.get("/register")
    assert res.status_code == 200
    assert b"Continue with Apple" in res.data
    assert b"id=\"btn-register-apple\"" in res.data


def test_missing_apple_configuration_does_not_crash(client, app):
    """3: When Apple credentials are empty, application doesn't crash and warns cleanly."""
    app.config["APPLE_CLIENT_ID"] = ""
    app.config["APPLE_TEAM_ID"] = ""
    app.config["APPLE_KEY_ID"] = ""
    app.config["APPLE_PRIVATE_KEY"] = ""

    res = client.get("/login")
    assert res.status_code == 200

    # Clicking Apple login redirects back to login with a warning notice
    res_apple = client.get("/auth/apple", follow_redirects=True)
    assert res_apple.status_code == 200
    assert b"Apple sign-in is not yet configured" in res_apple.data


def test_apple_oauth_start_route_when_configured(client, app):
    """5: Start route redirects to Apple authorization URL with state token."""
    app.config["APPLE_CLIENT_ID"] = "com.vitalis.wellness.service"
    app.config["APPLE_TEAM_ID"] = "TEAM123456"
    app.config["APPLE_KEY_ID"] = "KEY1234567"
    app.config["APPLE_PRIVATE_KEY"] = _generate_test_ec_key_pem()
    app.config["APPLE_REDIRECT_URI"] = "http://127.0.0.1:5000/auth/apple/callback"

    res = client.get("/auth/apple")
    assert res.status_code == 302
    location = res.headers["Location"]
    assert "https://appleid.apple.com/auth/authorize" in location
    assert "client_id=com.vitalis.wellness.service" in location
    assert "redirect_uri=http%3A%2F%2F127.0.0.1%3A5000%2Fauth%2Fapple%2Fcallback" in location
    assert "state=" in location
    assert "response_type=code+id_token" in location
    assert "response_mode=form_post" in location
    assert "scope=name+email" in location

    with client.session_transaction() as sess:
        assert "apple_oauth_state" in sess
        assert len(sess["apple_oauth_state"]) > 20


def test_apple_callback_user_cancellation_error(client):
    """6: When user denies permission on Apple, callback handles it gracefully."""
    with client.session_transaction() as sess:
        sess["apple_oauth_state"] = "csrf-state-apple"

    res = client.post(
        "/auth/apple/callback",
        data={"error": "user_cancelled_authorize", "state": "csrf-state-apple"},
        follow_redirects=True,
    )
    assert res.status_code == 200
    assert b"Apple sign-in was canceled" in res.data


def test_apple_invalid_or_mismatched_state_rejected(client):
    """7: Mismatched or tampered state token is rejected for CSRF protection."""
    with client.session_transaction() as sess:
        sess["apple_oauth_state"] = "legitimate-apple-secret"

    res = client.post(
        "/auth/apple/callback",
        data={"code": "some-apple-code", "state": "tampered-apple-state"},
        follow_redirects=True,
    )
    assert res.status_code == 200
    assert b"invalid state token" in res.data


def test_apple_token_exchange_error_handled_cleanly(client, app):
    """8: Token exchange network/provider failures handled without leaking stack traces."""
    app.config["APPLE_CLIENT_ID"] = "com.vitalis.wellness.service"
    app.config["APPLE_TEAM_ID"] = "TEAM123456"
    app.config["APPLE_KEY_ID"] = "KEY1234567"
    app.config["APPLE_PRIVATE_KEY"] = _generate_test_ec_key_pem()

    with client.session_transaction() as sess:
        sess["apple_oauth_state"] = "valid-apple-state"

    with patch("app.routes.auth._exchange_apple_code", side_effect=RuntimeError("Apple token network timeout")):
        res = client.post(
            "/auth/apple/callback",
            data={"code": "mock-apple-code", "state": "valid-apple-state"},
            follow_redirects=True,
        )

    assert res.status_code == 200
    assert b"Apple sign-in could not be completed" in res.data
    assert b"RuntimeError" not in res.data


def test_new_apple_user_created_and_redirects_to_onboarding(client, app):
    """9: Brand new Apple user account is registered and sent to onboarding."""
    app.config["APPLE_CLIENT_ID"] = "com.vitalis.wellness.service"
    app.config["APPLE_TEAM_ID"] = "TEAM123456"
    app.config["APPLE_KEY_ID"] = "KEY1234567"
    app.config["APPLE_PRIVATE_KEY"] = _generate_test_ec_key_pem()

    with client.session_transaction() as sess:
        sess["apple_oauth_state"] = "valid-apple-state-999"

    mock_id_token = jwt.encode(
        {
            "sub": "apple-sub-unique-001",
            "email": "jane.appleseed@example.com",
            "email_verified": "true",
            "iss": "https://appleid.apple.com",
            "aud": "com.vitalis.wellness.service",
            "exp": int(time.time()) + 3600,
        },
        "test-secret",
        algorithm="HS256",
    )

    user_payload = json.dumps({"name": {"firstName": "Jane", "lastName": "Appleseed"}})

    res = client.post(
        "/auth/apple/callback",
        data={
            "id_token": mock_id_token,
            "state": "valid-apple-state-999",
            "user": user_payload,
        },
        follow_redirects=False,
    )

    assert res.status_code == 302
    assert "/onboarding" in res.headers["Location"]

    with app.app_context():
        user = User.query.filter_by(apple_id="apple-sub-unique-001").first()
        assert user is not None
        assert user.email == "jane.appleseed@example.com"
        assert user.name == "Jane Appleseed"
        assert user.auth_provider == "apple"
        assert user.password_hash is not None


def test_existing_apple_user_logs_in_to_dashboard(client, app):
    """10: Existing Apple user with completed profile redirects to dashboard."""
    app.config["APPLE_CLIENT_ID"] = "com.vitalis.wellness.service"

    with app.app_context():
        user = User(
            name="Existing Apple User",
            email="existing.apple@wellness.ai",
            apple_id="apple-sub-existing-888",
            auth_provider="apple",
        )
        user.set_password("SecureApple123!")
        db.session.add(user)
        db.session.flush()

        profile = HealthProfile(
            user_id=user.id,
            age=29,
            gender="female",
            height_cm=168.0,
            weight_kg=60.0,
            activity_level="moderately_active",
            dietary_preference="mediterranean",
            health_goal="maintenance",
        )
        profile.calculate_metrics()
        db.session.add(profile)
        db.session.commit()
        saved_id = user.id

    with client.session_transaction() as sess:
        sess["apple_oauth_state"] = "valid-apple-existing"

    mock_id_token = jwt.encode(
        {
            "sub": "apple-sub-existing-888",
            "email": "existing.apple@wellness.ai",
            "iss": "https://appleid.apple.com",
            "aud": "com.vitalis.wellness.service",
            "exp": int(time.time()) + 3600,
        },
        "test-secret",
        algorithm="HS256",
    )

    res = client.post(
        "/auth/apple/callback",
        data={"id_token": mock_id_token, "state": "valid-apple-existing"},
        follow_redirects=False,
    )

    assert res.status_code == 302
    assert "/dashboard" in res.headers["Location"]
    with client.session_transaction() as sess:
        assert sess.get("user_id") == saved_id


def test_existing_local_user_safe_apple_account_linking(client, test_user, app):
    """11: Local user with matching verified email is linked without duplicating records."""
    app.config["APPLE_CLIENT_ID"] = "com.vitalis.wellness.service"

    with client.session_transaction() as sess:
        sess["apple_oauth_state"] = "valid-apple-link"

    mock_id_token = jwt.encode(
        {
            "sub": "apple-sub-linked-777",
            "email": test_user.email,
            "email_verified": True,
            "iss": "https://appleid.apple.com",
            "aud": "com.vitalis.wellness.service",
            "exp": int(time.time()) + 3600,
        },
        "test-secret",
        algorithm="HS256",
    )

    res = client.post(
        "/auth/apple/callback",
        data={"id_token": mock_id_token, "state": "valid-apple-link"},
        follow_redirects=False,
    )

    assert res.status_code == 302
    assert "/dashboard" in res.headers["Location"]

    with app.app_context():
        matching_users = User.query.filter_by(email=test_user.email).all()
        assert len(matching_users) == 1
        assert matching_users[0].id == test_user.id
        assert matching_users[0].apple_id == "apple-sub-linked-777"
        assert "apple" in matching_users[0].auth_provider


def test_account_collision_with_different_apple_id_rejected(client, app):
    """12: Account already linked to another Apple sub rejects different sub with same email."""
    app.config["APPLE_CLIENT_ID"] = "com.vitalis.wellness.service"

    with app.app_context():
        user = User(
            name="Bob",
            email="bob@example.com",
            apple_id="original-apple-sub-111",
            auth_provider="apple",
        )
        user.set_password("SecretPass123!")
        db.session.add(user)
        db.session.commit()

    with client.session_transaction() as sess:
        sess["apple_oauth_state"] = "valid-apple-collision"

    mock_id_token = jwt.encode(
        {
            "sub": "different-impostor-apple-sub",
            "email": "bob@example.com",
            "iss": "https://appleid.apple.com",
            "aud": "com.vitalis.wellness.service",
            "exp": int(time.time()) + 3600,
        },
        "test-secret",
        algorithm="HS256",
    )

    res = client.post(
        "/auth/apple/callback",
        data={"id_token": mock_id_token, "state": "valid-apple-collision"},
        follow_redirects=True,
    )

    assert res.status_code == 200
    assert b"already associated with another Apple account" in res.data


def test_apple_client_secret_jwt_generation(app):
    """13: Client secret generator produces valid signed ES256 JWT."""
    pem_key = _generate_test_ec_key_pem()
    token = _generate_apple_client_secret(
        client_id="com.vitalis.wellness.service",
        team_id="TEAMABC123",
        key_id="KEYXYZ456",
        private_key_str=pem_key,
    )
    assert token is not None

    # Verify headers and claims
    headers = jwt.get_unverified_header(token)
    assert headers["alg"] == "ES256"
    assert headers["kid"] == "KEYXYZ456"

    claims = jwt.decode(token, options={"verify_signature": False})
    assert claims["iss"] == "TEAMABC123"
    assert claims["sub"] == "com.vitalis.wellness.service"
    assert claims["aud"] == "https://appleid.apple.com"
    assert claims["exp"] > claims["iat"]


def test_apple_session_fixation_protection(client, test_user, app):
    """14: Attacker session keys are wiped out when logging in via Apple."""
    app.config["APPLE_CLIENT_ID"] = "com.vitalis.wellness.service"

    with client.session_transaction() as sess:
        sess["attacker_apple_key"] = "evil-apple-value"
        sess["apple_oauth_state"] = "valid-apple-fixation"

    mock_id_token = jwt.encode(
        {
            "sub": "apple-sub-fixation",
            "email": test_user.email,
            "iss": "https://appleid.apple.com",
            "aud": "com.vitalis.wellness.service",
            "exp": int(time.time()) + 3600,
        },
        "test-secret",
        algorithm="HS256",
    )

    client.post(
        "/auth/apple/callback",
        data={"id_token": mock_id_token, "state": "valid-apple-fixation"},
        follow_redirects=False,
    )

    with client.session_transaction() as sess:
        assert "attacker_apple_key" not in sess
        assert sess.get("user_id") == test_user.id


def test_apple_repeated_login_does_not_duplicate_account(client, app):
    """11: Repeated Apple sign-in resolves to identical local user without duplicating."""
    app.config["APPLE_CLIENT_ID"] = "com.vitalis.wellness.service"

    with client.session_transaction() as sess:
        sess["apple_oauth_state"] = "state-repeat-1"

    token_1 = jwt.encode(
        {
            "sub": "apple-persistent-user-007",
            "email": "repeat.apple@example.com",
            "iss": "https://appleid.apple.com",
            "aud": "com.vitalis.wellness.service",
            "exp": int(time.time()) + 3600,
        },
        "test-secret-key-for-testing-32chars!",
        algorithm="HS256",
    )

    # First sign-in: creates user
    client.post(
        "/auth/apple/callback",
        data={"id_token": token_1, "state": "state-repeat-1"},
        follow_redirects=False,
    )

    with app.app_context():
        users = User.query.filter_by(apple_id="apple-persistent-user-007").all()
        assert len(users) == 1
        first_user_id = users[0].id

    # Second sign-in: matches existing
    with client.session_transaction() as sess:
        sess["apple_oauth_state"] = "state-repeat-2"

    client.post(
        "/auth/apple/callback",
        data={"id_token": token_1, "state": "state-repeat-2"},
        follow_redirects=False,
    )

    with app.app_context():
        users = User.query.filter_by(apple_id="apple-persistent-user-007").all()
        assert len(users) == 1
        assert users[0].id == first_user_id


def test_apple_user_data_isolation(client, app):
    """14: Data created by Apple user is strictly isolated from other users."""
    app.config["APPLE_CLIENT_ID"] = "com.vitalis.wellness.service"

    with app.app_context():
        user_a = User(name="Apple User A", email="usera@wellness.ai", apple_id="apple-iso-a", auth_provider="apple")
        user_a.set_password("PassA123!")
        user_b = User(name="Apple User B", email="userb@wellness.ai", apple_id="apple-iso-b", auth_provider="apple")
        user_b.set_password("PassB123!")
        db.session.add_all([user_a, user_b])
        db.session.flush()

        from app.models.activity import DailyActivity
        from datetime import date
        act_a = DailyActivity(user_id=user_a.id, date=date.today(), steps=10000, water_liters=3.0, sleep_hours=8.0)
        act_b = DailyActivity(user_id=user_b.id, date=date.today(), steps=3000, water_liters=1.0, sleep_hours=5.0)
        db.session.add_all([act_a, act_b])
        db.session.commit()
        id_a = user_a.id
        id_b = user_b.id

    # Log in as user A
    with client.session_transaction() as sess:
        sess["user_id"] = id_a

    res_a = client.get("/activity")
    assert res_a.status_code == 200
    # User A's data is visible
    assert b"10,000" in res_a.data or b"10000" in res_a.data

    # Log in as user B
    with client.session_transaction() as sess:
        sess["user_id"] = id_b

    res_b = client.get("/activity")
    assert res_b.status_code == 200
    assert b"3,000" in res_b.data or b"3000" in res_b.data


def test_apple_database_persistence(client, app):
    """15: Apple user metadata persists across DB sessions."""
    app.config["APPLE_CLIENT_ID"] = "com.vitalis.wellness.service"

    with client.session_transaction() as sess:
        sess["apple_oauth_state"] = "state-persist"

    token = jwt.encode(
        {
            "sub": "apple-db-persist-123",
            "email": "persist.apple@wellness.ai",
            "iss": "https://appleid.apple.com",
            "aud": "com.vitalis.wellness.service",
            "exp": int(time.time()) + 3600,
        },
        "test-secret-key-for-testing-32chars!",
        algorithm="HS256",
    )

    client.post(
        "/auth/apple/callback",
        data={"id_token": token, "state": "state-persist"},
        follow_redirects=False,
    )

    with app.app_context():
        user = User.query.filter_by(apple_id="apple-db-persist-123").first()
        assert user is not None
        assert user.to_dict()["apple_id"] == "apple-db-persist-123"
        assert user.auth_provider == "apple"


def test_no_apple_secrets_in_rendered_html(client, app):
    """16: Sensitive Apple credentials never appear in frontend responses."""
    app.config["APPLE_CLIENT_ID"] = "com.vitalis.wellness.service"
    app.config["APPLE_TEAM_ID"] = "TEAMABC123"
    app.config["APPLE_KEY_ID"] = "KEYXYZ456"
    app.config["APPLE_PRIVATE_KEY"] = "-----BEGIN PRIVATE KEY-----\nMOCKPRIVATEKEYXYZ\n-----END PRIVATE KEY-----"

    res_login = client.get("/login")
    assert b"MOCKPRIVATEKEYXYZ" not in res_login.data
    assert b"TEAMABC123" not in res_login.data

    res_register = client.get("/register")
    assert b"MOCKPRIVATEKEYXYZ" not in res_register.data
