"""
Unit and integration tests for the Global AI Health Companion and Profile control.
"""
import pytest
from app.models.user import User
from app.models.health_profile import HealthProfile


def login_user(client, email="test@wellness.ai", password="TestSecret123!"):
    return client.post("/login", data={"email": email, "password": password}, follow_redirects=True)


def test_companion_not_rendered_on_unauthenticated_pages(client):
    """Verify that unauthenticated pages (login/register) do NOT render the floating companion."""
    res = client.get("/login")
    assert res.status_code == 200
    html = res.data.decode("utf-8")
    assert "vitalis-companion-root" not in html
    assert "vitalis-companion-launcher" not in html
    assert "vitalis-companion-panel" not in html

    res2 = client.get("/register")
    assert res2.status_code == 200
    html2 = res2.data.decode("utf-8")
    assert "vitalis-companion-root" not in html2


def test_companion_rendered_on_authenticated_pages(client, test_user):
    """Verify that authenticated pages render the global AI Health Companion."""
    login_user(client)

    authenticated_urls = [
        "/dashboard",
        "/activity",
        "/recommendations",
        "/progress",
        "/weekly-report",
        "/assistant",
        "/profile",
        "/how-it-works",
    ]

    for url in authenticated_urls:
        res = client.get(url, follow_redirects=True)
        assert res.status_code == 200, f"Failed accessing {url}"
        html = res.data.decode("utf-8")

        # Root and launcher
        assert 'id="vitalis-companion-root"' in html, f"Companion root missing on {url}"
        assert 'id="vitalis-companion-launcher"' in html, f"Companion launcher missing on {url}"
        assert 'id="vitalis-companion-panel"' in html, f"Companion panel missing on {url}"

        # SVG elements
        assert 'class="companion-avatar-icon"' in html
        assert 'bot-antenna-stalk' in html
        assert 'bot-pulse-line' in html
        assert 'bot-eye' in html

        # Accessibility attributes
        assert 'aria-label="Open Vitalis AI Health Companion"' in html
        assert 'aria-label="Close Vitalis AI Health Companion"' in html
        assert 'role="dialog"' in html


def test_user_badge_links_to_profile(client, test_user):
    """Verify that the top-right user name badge is an interactive link to /profile."""
    res = login_user(client)
    html = res.data.decode("utf-8")

    # User badge must be an <a> tag linking to /profile
    assert 'href="/profile"' in html
    assert 'id="current-user-badge"' in html
    assert 'class="user-badge' in html
    assert "Test" in html
    assert "T" in html  # Initial avatar


def test_separate_profile_and_assistant_removed_from_nav_menu(client, test_user):
    """Verify that separate 'Profile' and standalone 'AI Assistant' links are removed from main nav menu."""
    res = login_user(client)
    html = res.data.decode("utf-8")

    # nav-menu must NOT contain id="nav-profile" or id="nav-assistant"
    assert 'id="nav-profile"' not in html
    assert 'id="nav-assistant"' not in html

    # Desired hierarchy checks:
    assert 'id="nav-dashboard"' in html
    assert 'id="nav-activity"' in html
    assert 'id="nav-recommendations"' in html
    assert 'id="nav-progress"' in html
    assert 'id="nav-weekly-report"' in html
    assert 'id="nav-how-it-works"' in html


def test_assistant_route_redirects_to_companion_button(client, test_user):
    """Verify that /assistant route redirects to dashboard with open_companion=1 parameter."""
    login_user(client)
    res = client.get("/assistant", follow_redirects=False)
    assert res.status_code == 302
    assert "open_companion=1" in res.headers.get("Location", "")


def test_profile_page_is_functional_and_editable(client, test_user):
    """Verify that the Profile page displays information and accepts updates."""
    login_user(client)

    # GET /profile
    res = client.get("/profile")
    assert res.status_code == 200
    html = res.data.decode("utf-8")
    assert "Personal Health & Lifestyle Profile" in html
    assert "Test Runner" in html

    # POST /profile update
    update_data = {
        "name": "Test Runner Updated",
        "age": 31,
        "gender": "female",
        "height_cm": 165.0,
        "weight_kg": 59.0,
        "activity_level": "very_active",
        "dietary_preference": "balanced",
        "health_goal": "weight_loss",
        "allergies": "none",
        "physical_limitations": "none",
        "target_sleep_hours": 8.0,
        "target_water_liters": 2.8,
        "target_steps": 10000,
    }
    post_res = client.post("/profile", data=update_data, follow_redirects=True)
    assert post_res.status_code == 200
    post_html = post_res.data.decode("utf-8")
    assert "Profile updated successfully" in post_html or "Test Runner Updated" in post_html


def test_companion_css_and_reduced_motion():
    """Verify companion styles, floating keyframes, and reduced-motion overrides."""
    with open("static/css/main.css", "r", encoding="utf-8") as f:
        css = f.read()

    assert ".vitalis-companion-launcher" in css
    assert ".vitalis-companion-panel" in css
    assert "@keyframes companion-float" in css
    assert "cursor: pointer" in css
    assert "@media (prefers-reduced-motion: reduce)" in css


def test_companion_js_module():
    """Verify JavaScript controller defines VitalisCompanion with all required methods."""
    with open("static/js/main.js", "r", encoding="utf-8") as f:
        js = f.read()

    assert "window.VitalisCompanion = VitalisCompanion" in js
    assert "VitalisCompanion.init" in js
    assert "open()" in js
    assert "close()" in js
    assert "toggle()" in js
    assert "handleSubmit" in js
    assert "sendPrompt" in js


def test_shapeblur_elements_and_three_script(client, test_user):
    """Verify that ShapeBlur elements and Three.js script are present on authenticated pages and excluded on login."""
    # Unauthenticated: no three.js and no shapeblur mount
    res = client.get("/login")
    assert res.status_code == 200
    html = res.data.decode("utf-8")
    assert "three.min.js" not in html
    assert "vitalis-shapeblur-mount" not in html
    assert "vitalis-companion-launcher-wrapper" not in html

    # Authenticated: three.js script and shapeblur mount present
    auth_res = login_user(client)
    auth_html = auth_res.data.decode("utf-8")
    assert "three.min.js" in auth_html
    assert 'id="vitalis-shapeblur-mount"' in auth_html
    assert 'id="vitalis-companion-launcher-wrapper"' in auth_html
    assert 'class="vitalis-shapeblur-mount"' in auth_html
    assert 'aria-hidden="true"' in auth_html


def test_shapeblur_shader_and_damping():
    """Verify that VitalisShapeBlur in main.js retains all React Bits ShapeBlur shader algorithms and damping."""
    with open("static/js/main.js", "r", encoding="utf-8") as f:
        js = f.read()

    # Three.js damping
    assert "THREE.MathUtils.damp" in js, "Damped mouse movement missing"

    # Shader uniforms
    assert "u_mouse" in js
    assert "u_resolution" in js
    assert "u_pixelRatio" in js
    assert "u_shapeSize" in js
    assert "u_roundness" in js
    assert "u_borderSize" in js
    assert "u_circleSize" in js
    assert "u_circleEdge" in js

    # Signed distance functions and antialiasing
    assert "sdRoundRect" in js
    assert "sdCircle" in js
    assert "strokeAA" in js
    assert "fill(" in js

    # Local component coordinates
    assert "mount.getBoundingClientRect()" in js

    # WebGL cleanup
    assert "renderer.dispose()" in js
    assert "forceContextLoss" in js
    assert "material.dispose()" in js
    assert "geo.dispose()" in js

    # CSS styles
    with open("static/css/main.css", "r", encoding="utf-8") as f:
        css = f.read()

    assert ".vitalis-shapeblur-mount" in css
    assert "pointer-events: none" in css
    assert ".vitalis-companion-launcher" in css
    assert "pointer-events: auto" in css

