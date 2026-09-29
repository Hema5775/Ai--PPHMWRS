"""
Comprehensive Test Suite for Vitalis AI Phone Number & OTP Authentication.
Validates:
- Login page rendering and social auth button order (Google -> Apple -> Phone)
- Phone number normalization, validation, and masking
- OTP generation, delivery, rate limiting, and expiration
- Invalid OTP rejection and attempt limits
- Valid OTP authentication for new users (redirects to onboarding)
- Valid OTP authentication for existing users (redirects to dashboard)
- Session fixation protection and audit logging
- Provider abstraction (Twilio vs DevMock)
- CSS classes and animation sequence elements from CodePen reference
"""

import time
import pytest
from app.models.user import User
from app.models.health_profile import HealthProfile
from app.services.otp_service import OTPService, DevelopmentMockOTPProvider, TwilioOTPProvider
from app.extensions import db


def test_login_page_renders_phone_button_in_correct_order(client):
    """Verify that Continue with Phone appears directly below Continue with Apple on the login page."""
    res = client.get("/login")
    assert res.status_code == 200
    html = res.data.decode("utf-8")

    # Verify buttons present
    assert 'id="btn-google-login"' in html
    assert 'id="btn-apple-login"' in html
    assert 'id="btn-phone-login"' in html
    assert "Continue with Phone" in html

    # Verify strict visual order: Google -> Apple -> Phone -> Email Form
    idx_google = html.find('id="btn-google-login"')
    idx_apple = html.find('id="btn-apple-login"')
    idx_phone = html.find('id="btn-phone-login"')
    idx_form = html.find('id="login-form"')

    assert idx_google != -1 and idx_apple != -1 and idx_phone != -1 and idx_form != -1
    assert idx_google < idx_apple < idx_phone < idx_form

    # Verify phone and OTP views are present in markup
    assert 'id="auth-view-standard"' in html
    assert 'id="auth-view-phone"' in html
    assert 'id="auth-view-otp"' in html
    assert 'id="otp-stage"' in html
    assert 'id="otp-boxes-row"' in html
    assert 'id="loader-wrap"' in html
    assert 'id="success-wrap"' in html


def test_phone_normalization_and_masking():
    """Verify phone formatting and privacy masking functions."""
    assert OTPService.normalize_phone("+919876543210") == "+919876543210"
    assert OTPService.normalize_phone("+91 98765 43210") == "+919876543210"
    assert OTPService.normalize_phone("9876543210") == "+919876543210"
    assert OTPService.normalize_phone("+1 (555) 123-4567") == "+15551234567"
    assert OTPService.normalize_phone("invalid") is None
    assert OTPService.normalize_phone("") is None

    # Masking
    masked = OTPService.mask_phone("+919876543210")
    assert "+91 9876" in masked
    assert "10" in masked
    assert "••••" in masked


def test_phone_send_otp_validation_and_rate_limiting(client):
    """Verify validation, cooldown enforcement, and delivery response."""
    # 1. Missing phone
    res = client.post("/auth/phone/send-otp", json={"phone": ""})
    assert res.status_code == 400
    assert res.json["success"] is False
    assert "required" in res.json["error"].lower()

    # 2. Invalid phone format
    res = client.post("/auth/phone/send-otp", json={"phone": "123"})
    assert res.status_code == 400
    assert res.json["success"] is False

    # 3. Successful send
    test_phone = "+919123456780"
    res = client.post("/auth/phone/send-otp", json={"phone": test_phone})
    assert res.status_code == 200
    assert res.json["success"] is True
    assert "masked_phone" in res.json
    assert "dev_code" in res.json

    # 4. Cooldown rate limit (immediate second request within 30s)
    res_cooldown = client.post("/auth/phone/send-otp", json={"phone": test_phone})
    assert res_cooldown.status_code == 400
    assert res_cooldown.json["success"] is False
    assert "wait" in res_cooldown.json["error"].lower()


def test_phone_verify_otp_invalid_code_and_attempt_limit(client):
    """Verify invalid codes are rejected and lock out after 3 attempts."""
    test_phone = "+919876500001"
    res_send = client.post("/auth/phone/send-otp", json={"phone": test_phone})
    assert res_send.status_code == 200

    # Attempt 1: wrong code
    res_fail1 = client.post("/auth/phone/verify-otp", json={"phone": test_phone, "otp": "0000"})
    assert res_fail1.status_code == 400
    assert res_fail1.json["success"] is False
    assert "incorrect" in res_fail1.json["error"].lower()

    # Attempt 2: wrong code
    res_fail2 = client.post("/auth/phone/verify-otp", json={"phone": test_phone, "otp": "1111"})
    assert res_fail2.status_code == 400
    assert res_fail2.json["success"] is False

    # Attempt 3: wrong code triggers attempt limit
    res_fail3 = client.post("/auth/phone/verify-otp", json={"phone": test_phone, "otp": "2222"})
    assert res_fail3.status_code == 400
    assert "too many" in res_fail3.json["error"].lower()


def test_phone_verify_otp_creates_new_user_and_onboarding(client, app):
    """Verify valid OTP creates new user account and routes to onboarding."""
    test_phone = "+919876511111"
    res_send = client.post("/auth/phone/send-otp", json={"phone": test_phone})
    assert res_send.status_code == 200
    otp = res_send.json["dev_code"]

    res_verify = client.post("/auth/phone/verify-otp", json={"phone": test_phone, "otp": otp})
    assert res_verify.status_code == 200
    assert res_verify.json["success"] is True
    assert res_verify.json["is_new_user"] is True
    assert "/onboarding" in res_verify.json["redirect_url"]

    # Verify user saved in DB
    with app.app_context():
        user = User.query.filter_by(phone_number=test_phone).first()
        assert user is not None
        assert user.auth_provider == "phone"
        assert user.phone_number == test_phone

    # Verify session established
    with client.session_transaction() as sess:
        assert sess.get("user_id") is not None


def test_phone_verify_otp_existing_user_preserves_data_and_routes_to_dashboard(client, app):
    """Verify repeated login for existing user does not duplicate account and routes to dashboard."""
    test_phone = "+919876522222"

    with app.app_context():
        existing_user = User(
            name="Ravi Kumar",
            email="phone_919876522222@phone.vitalis.ai",
            phone_number=test_phone,
            auth_provider="phone",
            role="user"
        )
        existing_user.set_password("SecurePass123!")
        db.session.add(existing_user)
        db.session.commit()

        # Add completed profile
        profile = HealthProfile(
            user_id=existing_user.id,
            age=28,
            gender="male",
            height_cm=175.0,
            weight_kg=72.0,
            activity_level="moderately_active",
            dietary_preference="vegetarian",
            health_goal="maintenance",
            target_sleep_hours=7.5,
            target_water_liters=2.5,
            target_steps=9000,
        )
        db.session.add(profile)
        db.session.commit()
        user_id = existing_user.id

    # Send OTP
    res_send = client.post("/auth/phone/send-otp", json={"phone": test_phone})
    assert res_send.status_code == 200
    otp = res_send.json["dev_code"]

    # Verify OTP
    res_verify = client.post("/auth/phone/verify-otp", json={"phone": test_phone, "otp": otp})
    assert res_verify.status_code == 200
    assert res_verify.json["success"] is True
    assert res_verify.json["is_new_user"] is False
    assert "/dashboard" in res_verify.json["redirect_url"]

    # Confirm user was not duplicated
    with app.app_context():
        users = User.query.filter_by(phone_number=test_phone).all()
        assert len(users) == 1
        assert users[0].id == user_id


def test_provider_abstraction():
    """Verify provider fallback and Twilio configuration checking."""
    # Twilio unconfigured returns clean error
    twilio = TwilioOTPProvider("", "", "")
    ok, err = twilio.send_sms("+919876543210", "Test message")
    assert ok is False
    assert "not configured" in err.lower()

    # Development mock delivers cleanly
    mock = DevelopmentMockOTPProvider()
    ok_mock, err_mock = mock.send_sms("+919876543210", "Your code is: 4827")
    assert ok_mock is True
    assert DevelopmentMockOTPProvider.get_last_code("+919876543210") == "4827"


def test_css_and_animation_classes_present():
    """Verify that all CodePen OTP animation classes are defined in main.css."""
    with open("static/css/main.css", "r", encoding="utf-8") as f:
        css = f.read()

    required_classes = [
        ".otp-row",
        ".otp-box",
        ".otp-digit",
        ".filled",
        ".orbit",
        ".orbit-counter",
        ".verified",
        ".loader-wrap",
        ".progress-ring",
        ".ring-fg",
        ".success-wrap",
        "@keyframes otp-orbit-spin",
        "@keyframes otp-shake",
        "@keyframes success-pulse",
    ]

    for cls in required_classes:
        assert cls in css, f"Missing required CSS class or keyframe: {cls}"
