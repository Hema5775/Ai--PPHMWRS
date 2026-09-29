"""
Integration Tests for Admin ML Operations, Governance, and Rollback.
"""

from app.models.system_error import SystemErrorLog


def test_admin_dashboard_access(admin_client):
    res = admin_client.get("/admin/")
    assert res.status_code == 200
    assert b"Machine Learning & System Operations" in res.data


def test_admin_models_and_health(admin_client):
    res_models = admin_client.get("/admin/models")
    assert res_models.status_code == 200
    assert b"Model Registry" in res_models.data

    res_health = admin_client.get("/admin/model-health")
    assert res_health.status_code == 200
    assert b"Automated 11-Step ML Health" in res_health.data


def test_admin_errors_and_system_health(admin_client, app):
    with app.app_context():
        err = SystemErrorLog(
            error_id="SYS-ERR-9999",
            module="test_module",
            message="Simulated error message",
            severity="WARNING",
            category="ML",
            status="OPEN",
            safe_user_message="Safe user notification",
        )
        from app.extensions import db
        db.session.add(err)
        db.session.commit()

    res_err = admin_client.get("/admin/errors")
    assert res_err.status_code == 200
    assert b"SYS-ERR-9999" in res_err.data

    res_sys = admin_client.get("/admin/system-health")
    assert res_sys.status_code == 200
    assert b"Database Storage Layer" in res_sys.data


def test_admin_non_admin_forbidden(authenticated_client):
    # Non-admin user attempting to access /admin/ should be redirected
    res = authenticated_client.get("/admin/", follow_redirects=True)
    assert b"Administrative access required" in res.data
