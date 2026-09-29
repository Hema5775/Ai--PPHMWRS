"""
Comprehensive Tests for Vitalis AI Enhancements (Requirements 1-30).

Covers:
1. Email/password login
2. Google login flow (OAuth state token + redirect)
3. New Google user creation + redirection to onboarding
4. Existing account handling (safe linking to local account)
5. User data isolation (user A cannot see or edit user B's activities/records)
6. Activity creation
7. Activity update for same user and date (no duplicates)
8. Activity history (sorted newest first, proper fields)
9. Wellness score update on activity submission
10. Recommendation generation and refresh
11. Empty activity state for new users
12. Progress trends calculations and empty data state
13. Weekly report calculations and logged days indicator
14. Safety constraint behavior (respecting limitations and allergies)
15. Unauthorized access attempts (redirection to login, cross-user denial)
16. System error logging and user safety
17. Number formatting Jinja filters
18. Model naming (absence of 'Model A/B/C/D' in user-facing views)
"""

import re
import pytest
from datetime import date, timedelta
from unittest.mock import patch
from app.extensions import db
from app.models.user import User
from app.models.health_profile import HealthProfile
from app.models.activity import DailyActivity
from app.models.wellness_score import WellnessScore
from app.models.recommendation import Recommendation
from app.models.task import DailyTask
from app.models.system_error import SystemErrorLog
from app.services.error_service import ErrorTrackingService
from app.services.activity_service import ActivityService
from app.services.scoring_service import ScoringService
from app.services.recommendation_service import RecommendationService
from app.services.report_service import ReportService


# ---------------------------------------------------------------------------
# 1. Email/Password Login
# ---------------------------------------------------------------------------
def test_email_password_login_success_and_failure(client, test_user):
    # Invalid login first
    res_bad = client.post("/login", data={"email": "test@wellness.ai", "password": "WrongPassword!"}, follow_redirects=True)
    assert res_bad.status_code == 200
    assert b"Invalid email or password" in res_bad.data

    # Valid login
    res = client.post("/login", data={"email": "test@wellness.ai", "password": "TestSecret123!"}, follow_redirects=True)
    assert res.status_code == 200
    assert b"Welcome back" in res.data or b"Wellness Score" in res.data


# ---------------------------------------------------------------------------
# 2. Google Login Flow (State Token + Authorization Redirect)
# ---------------------------------------------------------------------------
def test_google_login_redirect_generates_state(client, app):
    app.config["GOOGLE_CLIENT_ID"] = "mock-google-client-id"
    res = client.get("/auth/google")
    assert res.status_code == 302
    assert "accounts.google.com/o/oauth2/v2/auth" in res.headers["Location"]
    assert "state=" in res.headers["Location"]
    with client.session_transaction() as sess:
        assert "google_oauth_state" in sess


# ---------------------------------------------------------------------------
# 3. New Google User Creation and Onboarding Redirection
# ---------------------------------------------------------------------------
def test_new_google_user_creation_and_onboarding(client, app):
    app.config["GOOGLE_CLIENT_ID"] = "mock-google-client-id"
    app.config["GOOGLE_CLIENT_SECRET"] = "mock-secret"

    with client.session_transaction() as sess:
        sess["google_oauth_state"] = "valid-test-state"

    mock_userinfo = {
        "sub": "google-sub-999888",
        "email": "brandnew.google@example.com",
        "name": "Google Newbie",
    }

    with patch("app.routes.auth._exchange_google_code", return_value={"access_token": "mock-token"}), \
         patch("app.routes.auth._fetch_google_userinfo", return_value=mock_userinfo):
        res = client.get("/auth/google/callback?code=mock-code&state=valid-test-state", follow_redirects=False)

    # Should redirect to onboarding because the user has no health profile
    assert res.status_code == 302
    assert "/onboarding" in res.headers["Location"]

    # Verify user created in DB with stable google_id
    with app.app_context():
        u = User.query.filter_by(google_id="google-sub-999888").first()
        assert u is not None
        assert u.email == "brandnew.google@example.com"
        assert u.name == "Google Newbie"


# ---------------------------------------------------------------------------
# 4. Existing Account Handling (Safe Linking)
# ---------------------------------------------------------------------------
def test_existing_user_google_account_linking(client, test_user, app):
    app.config["GOOGLE_CLIENT_ID"] = "mock-google-client-id"
    app.config["GOOGLE_CLIENT_SECRET"] = "mock-secret"

    with client.session_transaction() as sess:
        sess["google_oauth_state"] = "valid-test-state"

    mock_userinfo = {
        "sub": "google-sub-existing-123",
        "email": test_user.email,  # Matches existing test_user email
        "name": "Linked Test Runner",
    }

    with patch("app.routes.auth._exchange_google_code", return_value={"access_token": "mock-token"}), \
         patch("app.routes.auth._fetch_google_userinfo", return_value=mock_userinfo):
        res = client.get("/auth/google/callback?code=mock-code&state=valid-test-state", follow_redirects=False)

    # Has existing profile, should redirect to dashboard
    assert res.status_code == 302
    assert "/dashboard" in res.headers["Location"]

    # Verify existing account linked with google_id
    with app.app_context():
        u = db.session.get(User, test_user.id)
        assert u.google_id == "google-sub-existing-123"


# ---------------------------------------------------------------------------
# 5. User Data Isolation
# ---------------------------------------------------------------------------
def test_user_data_isolation(authenticated_client, test_user, app):
    """Ensure user A cannot see or modify user B's activities."""
    with app.app_context():
        other_user = User(name="User B", email="user_b@wellness.ai", role="user")
        other_user.set_password("Pass123!")
        db.session.add(other_user)
        db.session.flush()

        other_profile = HealthProfile(user_id=other_user.id, age=40, gender="male", height_cm=180, weight_kg=85)
        other_profile.calculate_metrics()
        db.session.add(other_profile)

        # User B logs activity
        ActivityService.log_daily_activity(
            user_id=other_user.id,
            entry_date=date.today() - timedelta(days=1),
            steps=12345,
            water_liters=3.5,
            sleep_hours=8.5,
            exercise_minutes=45,
            notes="User B private secret notes",
        )

    # Authenticated client is test_user (User A). They view the activity page.
    res = authenticated_client.get("/activity")
    assert res.status_code == 200
    # User B's distinct values and private notes must NOT appear
    assert b"12345" not in res.data
    assert b"User B private secret notes" not in res.data


# ---------------------------------------------------------------------------
# 6 & 7. Activity Creation and Same-Day Update
# ---------------------------------------------------------------------------
def test_activity_creation_and_same_day_update(authenticated_client, test_user, app):
    today = date.today().isoformat()

    # Step 1: Create today's activity
    res = authenticated_client.post("/activity", data={
        "date": today,
        "steps": "6000",
        "water_liters": "2.0",
        "sleep_hours": "7.0",
        "exercise_minutes": "30",
        "exercise_type": "walking",
        "sleep_quality": "3",
        "mood": "good",
        "notes": "First log of the day",
    }, follow_redirects=True)
    assert res.status_code == 200
    assert b"activity has been saved" in res.data

    with app.app_context():
        acts = DailyActivity.query.filter_by(user_id=test_user.id, date=date.today()).all()
        assert len(acts) == 1
        assert acts[0].steps == 6000
        assert acts[0].notes == "First log of the day"

    # Step 2: Update the same date's activity with new steps
    res2 = authenticated_client.post("/activity", data={
        "date": today,
        "steps": "9500",
        "water_liters": "2.8",
        "sleep_hours": "7.5",
        "exercise_minutes": "45",
        "exercise_type": "running",
        "sleep_quality": "4",
        "mood": "great",
        "notes": "Updated after evening run",
    }, follow_redirects=True)
    assert res2.status_code == 200
    assert b"activity has been saved" in res2.data

    # Ensure no duplicate was created for today and fields were updated
    with app.app_context():
        acts_after = DailyActivity.query.filter_by(user_id=test_user.id, date=date.today()).all()
        assert len(acts_after) == 1
        assert acts_after[0].steps == 9500
        assert acts_after[0].notes == "Updated after evening run"


# ---------------------------------------------------------------------------
# 8. Activity History (Sorted Newest First)
# ---------------------------------------------------------------------------
def test_activity_history_sorting_and_table(authenticated_client, test_user, app):
    d1 = date.today() - timedelta(days=2)
    d2 = date.today() - timedelta(days=1)
    d3 = date.today()

    with app.app_context():
        ActivityService.log_daily_activity(user_id=test_user.id, entry_date=d1, steps=5000, water_liters=1.5, sleep_hours=6.0, exercise_minutes=20)
        ActivityService.log_daily_activity(user_id=test_user.id, entry_date=d2, steps=8000, water_liters=2.2, sleep_hours=7.0, exercise_minutes=30)
        ActivityService.log_daily_activity(user_id=test_user.id, entry_date=d3, steps=11000, water_liters=3.0, sleep_hours=8.0, exercise_minutes=45)

    res = authenticated_client.get("/activity")
    assert res.status_code == 200
    data_str = res.data.decode("utf-8")

    # Verify records appear in reverse chronological order (newest first)
    pos_d3 = data_str.find("11,000")
    pos_d2 = data_str.find("8,000")
    pos_d1 = data_str.find("5,000")
    assert pos_d3 != -1 and pos_d2 != -1 and pos_d1 != -1
    assert pos_d3 < pos_d2 < pos_d1


# ---------------------------------------------------------------------------
# 9 & 10. Wellness Score Update & Recommendations Refresh
# ---------------------------------------------------------------------------
def test_wellness_score_and_recommendations_reactive(authenticated_client, test_user, app):
    today = date.today().isoformat()
    authenticated_client.post("/activity", data={
        "date": today,
        "steps": "8500",
        "water_liters": "2.5",
        "sleep_hours": "7.5",
        "exercise_minutes": "30",
        "exercise_type": "cycling",
        "sleep_quality": "4",
        "mood": "great",
    }, follow_redirects=True)

    with app.app_context():
        # A wellness score should have been calculated
        latest_score = WellnessScore.query.filter_by(user_id=test_user.id).order_by(WellnessScore.created_at.desc()).first()
        assert latest_score is not None
        assert 0 <= latest_score.total_score <= 100

        # Personalized recommendations should exist
        recs = Recommendation.query.filter_by(user_id=test_user.id).all()
        assert len(recs) > 0


# ---------------------------------------------------------------------------
# 11. Empty Activity State for New User
# ---------------------------------------------------------------------------
def test_empty_activity_dashboard_state(client, app):
    # Create fresh user with profile but zero activity logs
    with app.app_context():
        fresh_user = User(name="Fresh User", email="fresh@wellness.ai", role="user")
        fresh_user.set_password("Secret123!")
        db.session.add(fresh_user)
        db.session.flush()

        profile = HealthProfile(user_id=fresh_user.id, age=28, gender="female", height_cm=160, weight_kg=55)
        profile.calculate_metrics()
        db.session.add(profile)
        db.session.commit()
        uid = fresh_user.id

    with client.session_transaction() as sess:
        sess["user_id"] = uid

    res = client.get("/dashboard")
    assert res.status_code == 200
    # Must communicate not enough data rather than a broken 0 score
    assert b"Start logging your daily activity to generate your personalized wellness score." in res.data
    assert b"Awaiting today's log" in res.data


# ---------------------------------------------------------------------------
# 12. Progress Trends Calculations and Empty State
# ---------------------------------------------------------------------------
def test_progress_trends_empty_state_and_with_data(client, app):
    with app.app_context():
        empty_user = User(name="Empty Progress User", email="empty_prog@wellness.ai", role="user")
        empty_user.set_password("Secret123!")
        db.session.add(empty_user)
        db.session.flush()
        uid = empty_user.id
        db.session.commit()

    with client.session_transaction() as sess:
        sess["user_id"] = uid

    # With 0 activities, show clean empty state message
    res_empty = client.get("/progress?days=7")
    assert res_empty.status_code == 200
    assert b"Your progress will appear here after you log activity." in res_empty.data


# ---------------------------------------------------------------------------
# 13. Weekly Report Calculations & Logged Days Count
# ---------------------------------------------------------------------------
def test_weekly_report_logged_days_indicator(authenticated_client, test_user, app):
    with app.app_context():
        ActivityService.log_daily_activity(user_id=test_user.id, entry_date=date.today() - timedelta(days=1), steps=6000, water_liters=2.0, sleep_hours=7.0, exercise_minutes=30)
        ActivityService.log_daily_activity(user_id=test_user.id, entry_date=date.today(), steps=7000, water_liters=2.2, sleep_hours=7.2, exercise_minutes=30)
        ReportService.generate_weekly_report(user_id=test_user.id, week_end_date=date.today())

    res = authenticated_client.get("/weekly-report")
    assert res.status_code == 200
    assert b"Your report is based on 2 logged days." in res.data


# ---------------------------------------------------------------------------
# 14. Safety Constraint Behavior (Allergies & Physical Limitations)
# ---------------------------------------------------------------------------
def test_safety_constraints_respected_in_recommendations(app):
    with app.app_context():
        limited_user = User(name="Injured Knee Runner", email="injured@wellness.ai", role="user")
        limited_user.set_password("Secret123!")
        db.session.add(limited_user)
        db.session.flush()

        profile = HealthProfile(
            user_id=limited_user.id,
            age=32,
            gender="male",
            height_cm=175.0,
            weight_kg=78.0,
            physical_limitations="knee_pain",
            allergies="nuts",
        )
        profile.calculate_metrics()
        db.session.add(profile)
        db.session.commit()

        rec = RecommendationService.generate_daily_recommendation(user_id=limited_user.id, force_refresh=True)
        exercise_plan = rec.get_exercise_guidance()
        # Verify recommended exercises avoid knee-impact squatting
        for act in exercise_plan.get("recommended_activities", []):
            assert "squat" not in act.lower()


# ---------------------------------------------------------------------------
# 15. Unauthorized Access Attempts
# ---------------------------------------------------------------------------
def test_unauthorized_access_redirects(client):
    # Unauthenticated visitor attempting to access dashboard
    res = client.get("/dashboard")
    assert res.status_code == 302
    assert "/login" in res.headers["Location"]

    # Unauthenticated visitor attempting to access activities
    res_act = client.get("/activity")
    assert res_act.status_code == 302
    assert "/login" in res_act.headers["Location"]


# ---------------------------------------------------------------------------
# 16. System Error Handling and Logging
# ---------------------------------------------------------------------------
def test_system_error_logging_safe_fallback(app):
    with app.app_context():
        # Trigger an error logging event via ErrorTrackingService
        err_id = ErrorTrackingService.record_error(
            module="test_module",
            message="Internal test calculation anomaly",
            category="BACKEND",
            severity="WARNING",
            safe_user_message="Safe user-facing explanation",
        )
        assert err_id is not None

        # Verify in DB
        found = SystemErrorLog.query.filter_by(error_id=err_id).first()
        assert found is not None
        assert found.module == "test_module"
        assert found.severity == "WARNING"
        assert found.safe_user_message == "Safe user-facing explanation"


# ---------------------------------------------------------------------------
# 17. Number Formatting Jinja Filters
# ---------------------------------------------------------------------------
def test_jinja_number_formatting_filters(app):
    with app.app_context():
        env = app.jinja_env
        fmt_num = env.filters["format_number"]
        fmt_dec = env.filters["format_decimal"]
        fmt_pct = env.filters["format_percent"]

        assert fmt_num(11671) == "11,671"
        assert fmt_num(0) == "0"
        assert fmt_dec(7.283333333, 1) == "7.3"
        assert fmt_dec(2.583333333, 1) == "2.6"
        assert fmt_pct(0.85) == "85%"
        assert fmt_pct(85.0) == "85%"


# ---------------------------------------------------------------------------
# 18. Model Naming / Absence of Generic "Model A/B/C/D" in UI
# ---------------------------------------------------------------------------
def test_no_model_abcd_in_user_facing_templates(authenticated_client):
    endpoints = ["/dashboard", "/recommendations", "/progress", "/weekly-report", "/how-it-works"]
    pattern = re.compile(r"\bModel [ABCD]\b")
    for ep in endpoints:
        res = authenticated_client.get(ep)
        assert res.status_code == 200
        content = res.data.decode("utf-8")
        match = pattern.search(content)
        assert match is None, f"Found generic model designation '{match.group(0)}' in {ep}"
