"""
Database Schema & Relationship Integrity Tests.
"""

from datetime import date
from app.extensions import db
from app.models.user import User
from app.models.health_profile import HealthProfile
from app.models.activity import DailyActivity
from app.models.task import DailyTask
from app.models.wellness_score import WellnessScore
from app.models.audit_log import AuditLog
from app.models.system_error import SystemErrorLog


def test_database_relationships_and_cascades(app):
    with app.app_context():
        user = User(name="Cascade User", email="cascade@wellness.ai")
        user.set_password("Secret123!")
        db.session.add(user)
        db.session.flush()

        profile = HealthProfile(user_id=user.id, age=25, gender="male", height_cm=175.0, weight_kg=70.0)
        profile.calculate_metrics()
        db.session.add(profile)

        act = DailyActivity(user_id=user.id, date=date.today(), steps=6000, water_liters=2.0, sleep_hours=7.0, exercise_minutes=20)
        db.session.add(act)

        task = DailyTask(user_id=user.id, date=date.today(), title="Walk", target_description="6000 steps")
        db.session.add(task)

        db.session.commit()

        # Query user and verify relationships
        queried = User.query.get(user.id)
        assert queried.profile is not None
        assert queried.activities.count() == 1
        assert queried.tasks.count() == 1

        # Delete user and test cascade
        db.session.delete(queried)
        db.session.commit()

        assert HealthProfile.query.filter_by(user_id=user.id).first() is None
        assert DailyActivity.query.filter_by(user_id=user.id).first() is None
        assert DailyTask.query.filter_by(user_id=user.id).first() is None


def test_audit_and_error_logging(app):
    with app.app_context():
        audit = AuditLog(action="TEST_ACTION", details_json="{\"key\": \"val\"}")
        db.session.add(audit)

        err = SystemErrorLog(
            error_id="TEST-ERR-0001",
            module="tests",
            message="Test assertion message",
            severity="WARNING",
            safe_user_message="Safe user notification",
        )
        db.session.add(err)
        db.session.commit()

        assert AuditLog.query.filter_by(action="TEST_ACTION").first() is not None
        assert SystemErrorLog.query.filter_by(error_id="TEST-ERR-0001").first() is not None
