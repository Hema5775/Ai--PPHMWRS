"""
Unit and integration tests for Data Availability Service and
the 'How Vitalis AI Works' dynamic user states.
"""

from datetime import date, timedelta
from app.extensions import db
from app.models.user import User
from app.models.health_profile import HealthProfile
from app.models.activity import DailyActivity
from app.services.activity_service import ActivityService, get_user_data_availability


def _create_user_with_activity(email, name, days=0, has_profile=True, with_anomaly=False):
    """Helper to create a user with a given number of daily activity records."""
    user = User(name=name, email=email, role="user", is_demo=False)
    user.set_password("SecurePass123!")
    db.session.add(user)
    db.session.flush()

    if has_profile:
        profile = HealthProfile(
            user_id=user.id,
            age=29,
            gender="female",
            height_cm=168.0,
            weight_kg=63.0,
            activity_level="moderately_active",
            dietary_preference="balanced",
            health_goal="maintenance",
        )
        profile.calculate_metrics()
        db.session.add(profile)

    today = date.today()
    for i in range(days - 1, -1, -1):
        log_date = today - timedelta(days=i)
        is_anom = with_anomaly and (i == 0)
        act = DailyActivity(
            user_id=user.id,
            date=log_date,
            steps=25000 if is_anom else 7500,
            water_liters=2.5,
            sleep_hours=7.5,
            sleep_quality=4,
            exercise_minutes=45,
            calories_burned=2100,
            is_anomaly=is_anom,
            anomaly_reason="Statistical step outlier" if is_anom else None,
        )
        db.session.add(act)

    db.session.commit()
    return user


def test_alex_demo_user_populated_state(client, app):
    """1. Alex demo user with 30 days of seeded data receives SUFFICIENT state and NO empty banner."""
    with app.app_context():
        alex = _create_user_with_activity(
            email="demo@wellness.ai",
            name="Alex Taylor (Demo)",
            days=30,
            has_profile=True,
            with_anomaly=True,
        )
        alex_id = alex.id

    with client.session_transaction() as sess:
        sess["user_id"] = alex_id

    res = client.get("/how-it-works")
    assert res.status_code == 200
    html = res.data.decode("utf-8")

    # Populated state MUST appear
    assert "Your data is ready" in html
    assert "YOUR DATA IS READY" in html
    assert "Activity history available (30 days recorded)" in html

    # Empty state MUST NOT appear for Alex
    assert "NOT ENOUGH DATA YET" not in html
    assert "Still getting started?" not in html


def test_new_user_zero_activity_empty_state(client, app):
    """2. Genuinely new user with 0 activity receives NO DATA state and onboarding banner."""
    with app.app_context():
        newbie = _create_user_with_activity(
            email="newbie@wellness.ai",
            name="New User",
            days=0,
            has_profile=True,
        )
        newbie_id = newbie.id

    with client.session_transaction() as sess:
        sess["user_id"] = newbie_id

    res = client.get("/how-it-works")
    assert res.status_code == 200
    html = res.data.decode("utf-8")

    # Empty state MUST appear
    assert "Still getting started?" in html
    assert "NOT ENOUGH DATA YET" in html

    # Populated state MUST NOT appear
    assert "YOUR DATA IS READY" not in html


def test_partial_activity_partial_state(client, app):
    """3. User with partial activity (e.g. 3 days) receives PARTIAL state."""
    with app.app_context():
        partial_user = _create_user_with_activity(
            email="partial@wellness.ai",
            name="Partial User",
            days=3,
            has_profile=True,
        )
        partial_id = partial_user.id

    with client.session_transaction() as sess:
        sess["user_id"] = partial_id

    res = client.get("/how-it-works")
    assert res.status_code == 200
    html = res.data.decode("utf-8")

    # Partial state MUST appear
    assert "You're getting started" in html
    assert "SOME INSIGHTS AVAILABLE" in html
    assert "Initial activity logged (3 days)" in html

    # Neither NO DATA nor SUFFICIENT should be the primary status
    assert "NOT ENOUGH DATA YET" not in html
    assert "YOUR DATA IS READY" not in html


def test_sufficient_history_user_sufficient_state(client, app):
    """4. Normal (non-demo) user with >= 7 days of activity receives SUFFICIENT state."""
    with app.app_context():
        regular_user = _create_user_with_activity(
            email="regular@wellness.ai",
            name="Regular User",
            days=10,
            has_profile=True,
        )
        regular_id = regular_user.id

    with client.session_transaction() as sess:
        sess["user_id"] = regular_id

    res = client.get("/how-it-works")
    assert res.status_code == 200
    html = res.data.decode("utf-8")

    assert "Your data is ready" in html
    assert "YOUR DATA IS READY" in html
    assert "NOT ENOUGH DATA YET" not in html


def test_user_data_isolation(client, app):
    """5. User isolation: User B cannot accidentally receive User A's activity state."""
    with app.app_context():
        user_a = _create_user_with_activity("user_a@wellness.ai", "User A", days=14)
        user_b = _create_user_with_activity("user_b@wellness.ai", "User B", days=0)

        avail_a = ActivityService.get_user_data_availability(user_a)
        avail_b = ActivityService.get_user_data_availability(user_b)

        assert avail_a["state"] == "sufficient"
        assert avail_a["activity_count"] == 14

        assert avail_b["state"] == "no_data"
        assert avail_b["activity_count"] == 0


def test_activity_data_belongs_to_logged_in_user(client, app):
    """6. Ensure ActivityService.get_user_data_availability filters strictly by user_id."""
    with app.app_context():
        user_1 = _create_user_with_activity("u1@wellness.ai", "User 1", days=5)
        user_2 = _create_user_with_activity("u2@wellness.ai", "User 2", days=10)

        avail_1 = get_user_data_availability(user_1)
        avail_2 = get_user_data_availability(user_2)

        assert avail_1["activity_count"] == 5
        assert avail_1["state"] == "partial"

        assert avail_2["activity_count"] == 10
        assert avail_2["state"] == "sufficient"


def test_dashboard_and_how_it_works_consistent_context(client, app):
    """7. Dashboard and How It Works resolve consistent user data context."""
    with app.app_context():
        user = _create_user_with_activity("consistent@wellness.ai", "Consistent User", days=12)
        uid = user.id

    with client.session_transaction() as sess:
        sess["user_id"] = uid

    # Check dashboard
    dash_res = client.get("/dashboard")
    assert dash_res.status_code == 200

    # Check how-it-works
    hiw_res = client.get("/how-it-works")
    assert hiw_res.status_code == 200
    hiw_html = hiw_res.data.decode("utf-8")

    assert "Your data is ready" in hiw_html
    assert "Activity history available (12 days recorded)" in hiw_html


def test_no_hardcoded_alex_or_demo_conditionals():
    """8. Verify no hardcoded email or demo-name bypass exists in activity_service."""
    import inspect
    from app.services.activity_service import ActivityService

    src = inspect.getsource(ActivityService.get_user_data_availability)

    # Ensure no bypasses
    assert "demo@wellness.ai" not in src.lower()
    assert "alex" not in src.lower()
    assert "is_demo" not in src.lower()


def test_illustrative_example_labeled_and_not_fabricated_user_data(client):
    """9. Verify 60,000 steps is explicitly tagged as an illustrative example."""
    res = client.get("/how-it-works")
    html = res.data.decode("utf-8")

    assert "60,000 Steps" in html
    assert "Illustrative Example" in html or "Illustrative Typo" in html
    assert "Activity outlier detection flowchart" in html
