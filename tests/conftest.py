import sys
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

import pytest
from app import create_app
from app.extensions import db
from app.models.user import User
from app.models.health_profile import HealthProfile
from app.models.activity import DailyActivity
from app.models.task import DailyTask
from datetime import date


@pytest.fixture
def app():
    """Create and configure a clean test application instance."""
    app_instance = create_app("testing")
    with app_instance.app_context():
        db.create_all()
        yield app_instance
        db.session.remove()
        db.drop_all()


@pytest.fixture
def client(app):
    """A test client for the app."""
    return app.test_client()


@pytest.fixture
def test_user(app):
    """Seed a test user with a health profile."""
    user = User(name="Test Runner", email="test@wellness.ai", role="user")
    user.set_password("TestSecret123!")
    db.session.add(user)
    db.session.flush()

    profile = HealthProfile(
        user_id=user.id,
        age=30,
        gender="female",
        height_cm=165.0,
        weight_kg=60.0,
        activity_level="moderately_active",
        dietary_preference="balanced",
        health_goal="maintenance",
        physical_limitations="none",
        allergies="",
    )
    profile.calculate_metrics()
    db.session.add(profile)
    db.session.commit()
    return user


@pytest.fixture
def authenticated_client(client, test_user):
    """A test client logged in as test_user."""
    with client.session_transaction() as sess:
        sess["user_id"] = test_user.id
    return client


@pytest.fixture
def admin_user(app):
    """Seed an admin user."""
    admin = User(name="Admin Runner", email="admin_test@wellness.ai", role="admin")
    admin.set_password("AdminSecret123!")
    db.session.add(admin)
    db.session.commit()
    return admin


@pytest.fixture
def admin_client(client, admin_user):
    """A test client logged in as admin_user."""
    with client.session_transaction() as sess:
        sess["user_id"] = admin_user.id
    return client
