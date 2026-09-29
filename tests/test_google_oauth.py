"""
Comprehensive unit and integration tests for Google OAuth 2.0 authentication flow.
Tests coverage:
1. Login page loads successfully.
2. Google button is present in HTML.
3. Missing Google configuration does not crash the application.
4. Email/password login continues to work normally.
5. Google OAuth start route redirects correctly when configured.
6. OAuth callback handles provider errors (e.g., user cancellation).
7. Invalid or missing OAuth state token (CSRF) is rejected.
8. Token exchange/network failures handled cleanly with friendly messages.
9. New Google user account created with onboarding redirection.
10. Existing Google user logs in directly to dashboard.
11. Existing local account is safely linked without duplicating user.
12. Account collision with mismatched Google subject is rejected.
13. Unverified Google email is rejected.
14. Session fixation defense and session state established.
15. Logout clears session completely.
16. No client secrets leaked in HTML or logs.
"""

import urllib.parse
from unittest.mock import patch, MagicMock
from app.extensions import db
from app.models.user import User
from app.models.health_profile import HealthProfile
from app.routes.auth import _verify_and_extract_google_identity, _get_google_redirect_uri


def test_login_page_loads_and_google_button_present(client):
    """1 & 2: Login page loads and contains the Google sign-in button."""
    res = client.get("/login")
    assert res.status_code == 200
    assert b"Continue with Google" in res.data
    assert b"id=\"btn-google-login\"" in res.data
    assert b"Sign In" in res.data


def test_missing_google_configuration_does_not_crash(client, app):
    """3: When Google credentials are empty, application doesn't crash and warns cleanly."""
    app.config["GOOGLE_CLIENT_ID"] = ""
    app.config["GOOGLE_CLIENT_SECRET"] = ""

    # GET login should succeed
    res = client.get("/login")
    assert res.status_code == 200

    # Clicking Google login redirects back to login with a warning notice
    res_google = client.get("/auth/google", follow_redirects=True)
    assert res_google.status_code == 200
    assert b"Google sign-in is not yet configured" in res_google.data


def test_google_oauth_no_hardcoded_login_hint_or_hd(client, app):
    """Verify authorization URL does NOT contain login_hint or hd, and uses prompt=select_account."""
    app.config["GOOGLE_CLIENT_ID"] = "test-client-12345.apps.googleusercontent.com"
    app.config["GOOGLE_CLIENT_SECRET"] = "test-secret"
    app.config["GOOGLE_REDIRECT_URI"] = "http://127.0.0.1:5000/auth/google/callback"

    res = client.get("/auth/google")
    assert res.status_code == 302
    location = res.headers["Location"]
    parsed = urllib.parse.urlparse(location)
    params = urllib.parse.parse_qs(parsed.query)

    # 1. Must use prompt=select_account to allow multi-account selection
    assert params.get("prompt") == ["select_account"]

    # 2. Must NOT contain login_hint (no forced or pre-selected email)
    assert "login_hint" not in params

    # 3. Must NOT contain hd (no domain restriction)
    assert "hd" not in params

    # 4. Must preserve state/CSRF
    assert "state" in params
    assert len(params["state"][0]) > 20


def test_email_password_login_works_with_oauth_enabled(client, test_user, app):
    """4: Email/password authentication remains fully operational."""
    app.config["GOOGLE_CLIENT_ID"] = "mock-client-id"
    app.config["GOOGLE_CLIENT_SECRET"] = "mock-client-secret"

    res = client.post(
        "/login",
        data={"email": "test@wellness.ai", "password": "TestSecret123!"},
        follow_redirects=True,
    )
    assert res.status_code == 200
    assert b"Welcome back" in res.data
    with client.session_transaction() as sess:
        assert sess.get("user_id") == test_user.id


def test_google_oauth_start_route_when_configured(client, app):
    """5: Start route redirects to Google authorization URL with state token."""
    app.config["GOOGLE_CLIENT_ID"] = "test-client-12345.apps.googleusercontent.com"
    app.config["GOOGLE_CLIENT_SECRET"] = "test-secret"
    app.config["GOOGLE_REDIRECT_URI"] = "http://127.0.0.1:5000/auth/google/callback"

    res = client.get("/auth/google")
    assert res.status_code == 302
    location = res.headers["Location"]
    assert "https://accounts.google.com/o/oauth2/v2/auth" in location
    assert "client_id=test-client-12345.apps.googleusercontent.com" in location
    assert "redirect_uri=http%3A%2F%2F127.0.0.1%3A5000%2Fauth%2Fgoogle%2Fcallback" in location
    assert "state=" in location
    assert "scope=openid+email+profile" in location

    with client.session_transaction() as sess:
        assert "google_oauth_state" in sess
        assert len(sess["google_oauth_state"]) > 20


def test_oauth_callback_user_denial_error(client):
    """6: When user denies permission on Google, callback handles it gracefully."""
    with client.session_transaction() as sess:
        sess["google_oauth_state"] = "csrf-state-abc"

    res = client.get("/auth/google/callback?error=access_denied&state=csrf-state-abc", follow_redirects=True)
    assert res.status_code == 200
    assert b"Google sign-in was canceled" in res.data


def test_invalid_or_mismatched_state_rejected(client):
    """7: Mismatched or tampered state token is rejected for CSRF protection."""
    with client.session_transaction() as sess:
        sess["google_oauth_state"] = "legitimate-secret-token"

    res = client.get("/auth/google/callback?code=some-code&state=tampered-token", follow_redirects=True)
    assert res.status_code == 200
    assert b"invalid state token" in res.data


def test_token_exchange_error_handled_cleanly(client, app):
    """8: Token exchange network/provider failures handled without leaking stack traces."""
    app.config["GOOGLE_CLIENT_ID"] = "mock-id"
    app.config["GOOGLE_CLIENT_SECRET"] = "mock-secret"

    with client.session_transaction() as sess:
        sess["google_oauth_state"] = "valid-state"

    with patch("app.routes.auth._exchange_google_code", side_effect=RuntimeError("Google token network timeout")):
        res = client.get("/auth/google/callback?code=mock-code&state=valid-state", follow_redirects=True)

    assert res.status_code == 200
    assert b"Google sign-in could not be completed" in res.data
    # Ensure raw exception name is not displayed in HTML
    assert b"RuntimeError" not in res.data


def test_new_google_user_created_and_redirects_to_onboarding(client, app):
    """9: Brand new Google user account is registered and sent to onboarding."""
    app.config["GOOGLE_CLIENT_ID"] = "mock-id"
    app.config["GOOGLE_CLIENT_SECRET"] = "mock-secret"

    with client.session_transaction() as sess:
        sess["google_oauth_state"] = "valid-state-999"

    mock_userinfo = {
        "sub": "google-sub-unique-777",
        "email": "new.wellness.user@example.com",
        "name": "Sarah Connor",
        "email_verified": True,
    }

    with patch("app.routes.auth._exchange_google_code", return_value={"access_token": "mock-token"}), \
         patch("app.routes.auth._fetch_google_userinfo", return_value=mock_userinfo):
        res = client.get("/auth/google/callback?code=mock-code&state=valid-state-999", follow_redirects=False)

    assert res.status_code == 302
    assert "/onboarding" in res.headers["Location"]

    with app.app_context():
        user = User.query.filter_by(google_id="google-sub-unique-777").first()
        assert user is not None
        assert user.email == "new.wellness.user@example.com"
        assert user.name == "Sarah Connor"
        assert user.auth_provider == "google"
        assert user.password_hash is not None


def test_existing_google_user_logs_in_to_dashboard(client, app):
    """10: Existing Google user with completed profile redirects to dashboard."""
    app.config["GOOGLE_CLIENT_ID"] = "mock-id"
    app.config["GOOGLE_CLIENT_SECRET"] = "mock-secret"

    with app.app_context():
        user = User(
            name="Existing Google User",
            email="existing.google@wellness.ai",
            google_id="google-sub-existing-444",
            auth_provider="google",
        )
        user.set_password("SecurePass123!")
        db.session.add(user)
        db.session.flush()

        profile = HealthProfile(
            user_id=user.id,
            age=32,
            gender="male",
            height_cm=175.0,
            weight_kg=72.0,
            activity_level="moderately_active",
            dietary_preference="balanced",
            health_goal="maintenance",
        )
        profile.calculate_metrics()
        db.session.add(profile)
        db.session.commit()
        saved_id = user.id

    with client.session_transaction() as sess:
        sess["google_oauth_state"] = "valid-state-existing"

    mock_userinfo = {
        "sub": "google-sub-existing-444",
        "email": "existing.google@wellness.ai",
        "name": "Existing Google User",
        "email_verified": True,
    }

    with patch("app.routes.auth._exchange_google_code", return_value={"access_token": "mock-token"}), \
         patch("app.routes.auth._fetch_google_userinfo", return_value=mock_userinfo):
        res = client.get("/auth/google/callback?code=mock-code&state=valid-state-existing", follow_redirects=False)

    assert res.status_code == 302
    assert "/dashboard" in res.headers["Location"]
    with client.session_transaction() as sess:
        assert sess.get("user_id") == saved_id


def test_existing_local_user_safe_account_linking(client, test_user, app):
    """11: Local user with matching verified email is linked without duplicating records."""
    app.config["GOOGLE_CLIENT_ID"] = "mock-id"
    app.config["GOOGLE_CLIENT_SECRET"] = "mock-secret"

    with client.session_transaction() as sess:
        sess["google_oauth_state"] = "valid-state-link"

    mock_userinfo = {
        "sub": "google-sub-linked-888",
        "email": test_user.email,
        "name": "Test Runner",
        "email_verified": True,
    }

    with patch("app.routes.auth._exchange_google_code", return_value={"access_token": "mock-token"}), \
         patch("app.routes.auth._fetch_google_userinfo", return_value=mock_userinfo):
        res = client.get("/auth/google/callback?code=mock-code&state=valid-state-link", follow_redirects=False)

    assert res.status_code == 302
    assert "/dashboard" in res.headers["Location"]

    with app.app_context():
        # Check no duplicate user was created
        matching_users = User.query.filter_by(email=test_user.email).all()
        assert len(matching_users) == 1
        assert matching_users[0].id == test_user.id
        assert matching_users[0].google_id == "google-sub-linked-888"


def test_account_collision_with_different_google_id_rejected(client, app):
    """12: Account already linked to another Google sub rejects different sub with same email."""
    app.config["GOOGLE_CLIENT_ID"] = "mock-id"
    app.config["GOOGLE_CLIENT_SECRET"] = "mock-secret"

    with app.app_context():
        user = User(
            name="Alice",
            email="alice@example.com",
            google_id="original-google-sub-111",
            auth_provider="google",
        )
        user.set_password("SecretPass123!")
        db.session.add(user)
        db.session.commit()

    with client.session_transaction() as sess:
        sess["google_oauth_state"] = "valid-state-collision"

    mock_userinfo = {
        "sub": "different-impostor-sub-999",
        "email": "alice@example.com",
        "name": "Alice",
        "email_verified": True,
    }

    with patch("app.routes.auth._exchange_google_code", return_value={"access_token": "mock-token"}), \
         patch("app.routes.auth._fetch_google_userinfo", return_value=mock_userinfo):
        res = client.get("/auth/google/callback?code=mock-code&state=valid-state-collision", follow_redirects=True)

    assert res.status_code == 200
    assert b"already associated with another Google account" in res.data


def test_unverified_google_email_rejected(client, app):
    """13: Unverified email addresses from Google are rejected for security."""
    app.config["GOOGLE_CLIENT_ID"] = "mock-id"
    app.config["GOOGLE_CLIENT_SECRET"] = "mock-secret"

    with client.session_transaction() as sess:
        sess["google_oauth_state"] = "valid-state-unverified"

    mock_userinfo = {
        "sub": "google-sub-unverified",
        "email": "unverified@example.com",
        "name": "Unverified User",
        "email_verified": False,
    }

    with patch("app.routes.auth._exchange_google_code", return_value={"access_token": "mock-token"}), \
         patch("app.routes.auth._fetch_google_userinfo", return_value=mock_userinfo):
        res = client.get("/auth/google/callback?code=mock-code&state=valid-state-unverified", follow_redirects=True)

    assert res.status_code == 200
    assert b"not verified by Google" in res.data


def test_session_fixation_protection_and_session_created(client, test_user, app):
    """14: Session is cleanly cleared and regenerated upon authentication."""
    app.config["GOOGLE_CLIENT_ID"] = "mock-id"
    app.config["GOOGLE_CLIENT_SECRET"] = "mock-secret"

    # Pre-populate session with attacker data
    with client.session_transaction() as sess:
        sess["attacker_fixated_key"] = "evil-value"
        sess["google_oauth_state"] = "valid-state-fixation"

    mock_userinfo = {
        "sub": "google-sub-fixation",
        "email": test_user.email,
        "name": "Test Runner",
        "email_verified": True,
    }

    with patch("app.routes.auth._exchange_google_code", return_value={"access_token": "mock-token"}), \
         patch("app.routes.auth._fetch_google_userinfo", return_value=mock_userinfo):
        client.get("/auth/google/callback?code=mock-code&state=valid-state-fixation", follow_redirects=False)

    with client.session_transaction() as sess:
        # Pre-existing keys must be wiped out
        assert "attacker_fixated_key" not in sess
        assert sess.get("user_id") == test_user.id


def test_logout_clears_session_completely(authenticated_client):
    """15: Logout erases all session variables."""
    res = authenticated_client.get("/logout", follow_redirects=True)
    assert res.status_code == 200
    assert b"logged out" in res.data

    with authenticated_client.session_transaction() as sess:
        assert "user_id" not in sess
        assert len(sess) == 0


def test_no_secrets_in_rendered_html(client, app):
    """16: Sensitive client secret never appears in frontend responses."""
    app.config["GOOGLE_CLIENT_ID"] = "visible-client-id-12345.apps.googleusercontent.com"
    app.config["GOOGLE_CLIENT_SECRET"] = "SUPER-SECRET-OAUTH-SECRET-XYZ-999"

    res_login = client.get("/login")
    assert b"SUPER-SECRET-OAUTH-SECRET-XYZ-999" not in res_login.data

    res_register = client.get("/register")
    assert b"SUPER-SECRET-OAUTH-SECRET-XYZ-999" not in res_register.data


def test_google_repeated_login_does_not_duplicate_account(client, app):
    """17: Repeated Google sign-ins for same user must not create duplicate user records."""
    app.config["GOOGLE_CLIENT_ID"] = "mock-id"
    app.config["GOOGLE_CLIENT_SECRET"] = "mock-secret"

    mock_userinfo = {
        "sub": "google-persistent-sub-12345",
        "email": "repeat.google@example.com",
        "name": "Repeat Google User",
        "email_verified": True,
    }

    # First login
    with client.session_transaction() as sess:
        sess["google_oauth_state"] = "state-google-1"

    with patch("app.routes.auth._exchange_google_code", return_value={"access_token": "mock-token"}), \
         patch("app.routes.auth._fetch_google_userinfo", return_value=mock_userinfo):
        client.get("/auth/google/callback?code=mock-code&state=state-google-1", follow_redirects=False)

    with app.app_context():
        users = User.query.filter_by(google_id="google-persistent-sub-12345").all()
        assert len(users) == 1
        initial_id = users[0].id

    # Second login
    with client.session_transaction() as sess:
        sess["google_oauth_state"] = "state-google-2"

    with patch("app.routes.auth._exchange_google_code", return_value={"access_token": "mock-token"}), \
         patch("app.routes.auth._fetch_google_userinfo", return_value=mock_userinfo):
        client.get("/auth/google/callback?code=mock-code&state=state-google-2", follow_redirects=False)

    with app.app_context():
        users = User.query.filter_by(google_id="google-persistent-sub-12345").all()
        assert len(users) == 1
        assert users[0].id == initial_id


def test_google_user_data_isolation(client, app):
    """18: Google user activity and recommendations remain strictly isolated."""
    app.config["GOOGLE_CLIENT_ID"] = "mock-id"
    app.config["GOOGLE_CLIENT_SECRET"] = "mock-secret"

    with app.app_context():
        user_g1 = User(name="Google User 1", email="guser1@wellness.ai", google_id="g-sub-iso-1", auth_provider="google")
        user_g1.set_password("Secret123!")
        user_g2 = User(name="Google User 2", email="guser2@wellness.ai", google_id="g-sub-iso-2", auth_provider="google")
        user_g2.set_password("Secret456!")
        db.session.add_all([user_g1, user_g2])
        db.session.flush()

        from app.models.activity import DailyActivity
        from datetime import date
        act1 = DailyActivity(user_id=user_g1.id, date=date.today(), steps=12000, water_liters=3.5, sleep_hours=8.5)
        act2 = DailyActivity(user_id=user_g2.id, date=date.today(), steps=4500, water_liters=1.5, sleep_hours=6.0)
        db.session.add_all([act1, act2])
        db.session.commit()
        id1 = user_g1.id
        id2 = user_g2.id

    with client.session_transaction() as sess:
        sess["user_id"] = id1

    res1 = client.get("/activity")
    assert res1.status_code == 200
    assert b"12,000" in res1.data or b"12000" in res1.data

    with client.session_transaction() as sess:
        sess["user_id"] = id2

    res2 = client.get("/activity")
    assert res2.status_code == 200
    assert b"4,500" in res2.data or b"4500" in res2.data
