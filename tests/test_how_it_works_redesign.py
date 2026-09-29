"""
Tests for the redesigned 'How Vitalis AI Works' interactive page.
Validates structure, accessibility, React Bits component integration,
technical architecture preservation, and fallback hierarchy.
"""

import os
import re
import pytest
from app.models.user import User


def test_how_it_works_route_unauthenticated(client):
    """Verify that /how-it-works is accessible to unauthenticated visitors."""
    res = client.get("/how-it-works")
    assert res.status_code == 200
    html = res.data.decode("utf-8")
    assert "How Vitalis AI Works" in html
    assert "YOUR PERSONAL WELLNESS COMPANION" in html


def test_how_it_works_route_authenticated(client, test_user):
    """Verify that /how-it-works is accessible when logged in, with companion and user badge."""
    with client.session_transaction() as sess:
        sess["user_id"] = test_user.id
        sess["user_email"] = test_user.email

    res = client.get("/how-it-works")
    assert res.status_code == 200
    html = res.data.decode("utf-8")

    # Navbar link active
    assert 'id="nav-how-it-works"' in html

    # AI Companion active
    assert 'id="vitalis-companion-root"' in html
    assert 'id="vitalis-companion-launcher"' in html

    # Profile badge active
    assert 'id="current-user-badge"' in html


def test_hero_and_information_pipeline(client):
    """Verify hero section texts and the 5-node visual flow pipeline."""
    res = client.get("/how-it-works")
    html = res.data.decode("utf-8")

    # Eyebrow, heading, and subtitle
    assert "YOUR PERSONAL WELLNESS COMPANION" in html
    assert "How Vitalis AI Works" in html
    assert "Vitalis AI turns your everyday wellness data into understandable insights" in html

    # Hero visual flow nodes
    assert "Your Data" in html
    assert "Intelligence" in html
    assert "Personalization" in html
    assert "Guidance" in html
    assert "Progress" in html


def test_journey_timeline_stages(client):
    """Verify the 4-stage Data -> Insight -> Action user journey."""
    res = client.get("/how-it-works")
    html = res.data.decode("utf-8")

    assert "From your data to your next step" in html
    assert "01" in html
    assert "Track" in html
    assert "Log everyday activities such as movement, sleep, hydration, and completed tasks." in html

    assert "02" in html
    assert "Understand" in html
    assert "Vitalis looks at recent activity and profile information to identify meaningful patterns." in html

    assert "03" in html
    assert "Personalize" in html
    assert "Your profile, goals, history, and available data are considered before guidance is presented." in html

    assert "04" in html
    assert "Act" in html
    assert "Receive practical recommendations and small achievable actions you can follow." in html


def test_five_core_capabilities_preserved_with_exact_names_and_ids(client):
    """Verify all 5 core capabilities preserve exact names, IDs, and no generic Model A/B/C/D."""
    res = client.get("/how-it-works")
    html = res.data.decode("utf-8")

    # Required DOM IDs
    required_ids = [
        "info-recommendations",
        "info-wellness-score",
        "info-progress-trends",
        "info-activity-insights",
        "info-safety"
    ]
    for dom_id in required_ids:
        assert f'id="{dom_id}"' in html, f"Missing required capability DOM ID '{dom_id}'"

    # Exact user-facing names
    assert "Personalized Recommendations" in html
    assert "Wellness Score" in html
    assert "Progress Trends" in html
    assert "Activity Insights" in html
    assert "Safety & Personalization" in html

    # Fast-jump navigation pills
    assert 'id="nav-btn-recommendations"' in html
    assert 'id="nav-btn-score"' in html
    assert 'id="nav-btn-trends"' in html
    assert 'id="nav-btn-insights"' in html
    assert 'id="nav-btn-safety"' in html

    # No generic Model A/B/C/D designation
    assert re.search(r"\bModel [ABCD]\b", html) is None


def test_wellness_score_visualization_and_breakdown(client):
    """Verify wellness score card displays 0-100 gauge, 5 weighted dimensions, and example label."""
    res = client.get("/how-it-works")
    html = res.data.decode("utf-8")

    # Illustrative label
    assert "Illustrative Example" in html
    assert 'id="hiw-score-num"' in html
    assert 'id="hiw-radial-val"' in html

    # 5 weighted dimensions
    assert "Activity" in html
    assert "25%" in html
    assert "Hydration" in html
    assert "20%" in html
    assert "Sleep" in html
    assert "Daily Tasks" in html
    assert "7-day Logging Consistency" in html
    assert "15%" in html

    # What it means & What it is not
    assert "What it means" in html
    assert "What it is not" in html
    assert "clinical pathology" in html


def test_progress_trends_and_horizons(client):
    """Verify progress trends card includes 7, 14, and 30 day horizon tabs."""
    res = client.get("/how-it-works")
    html = res.data.decode("utf-8")

    assert 'id="tab-7d"' in html
    assert 'id="tab-14d"' in html
    assert 'id="tab-30d"' in html
    assert 'id="hiw-trend-path"' in html
    assert "Looking across multiple time windows helps reveal" in html


def test_activity_insights_outlier_flow(client):
    """Verify activity insights outlier flow with 60,000 steps example."""
    res = client.get("/how-it-works")
    html = res.data.decode("utf-8")

    assert "60,000 Steps" in html
    assert "Statistical Outlier" in html
    assert "Review / Flag Notice" in html
    assert "flag unusual entries or possible logging mistakes" in html


def test_safety_and_personalization_filter(client):
    """Verify safety & personalization constraint layer nodes."""
    res = client.get("/how-it-works")
    html = res.data.decode("utf-8")

    assert "Safety & Personalization" in html
    assert "Profile Data" in html
    assert "Goals" in html
    assert "Constraints" in html
    assert "Data Quality" in html
    assert "knee sensitivity" in html
    assert "allergies" in html


def test_quality_inputs_and_cold_start_sections(client):
    """Verify 'Better inputs -> More useful guidance' and 'Still getting started?' sections."""
    res = client.get("/how-it-works")
    html = res.data.decode("utf-8")

    assert "Better inputs" in html
    assert "Tell Vitalis about yourself and your wellness objective." in html
    assert "Keep your daily activity information reasonably consistent." in html
    assert "Review recommendations and progress rather than blindly following them." in html
    assert "Keep your profile and goals current when they change." in html

    # Cold start
    assert "Still getting started?" in html
    assert "NOT ENOUGH DATA YET" in html
    assert "Vitalis does not require a perfect history." in html


def test_usage_habits_and_safe_fallback(client):
    """Verify 'How to use Vitalis effectively' and 'Designed to fail safely' sections."""
    res = client.get("/how-it-works")
    html = res.data.decode("utf-8")

    assert "How to use Vitalis effectively" in html
    assert "Complete your profile" in html
    assert "Log consistently" in html
    assert "Review your recommendations" in html
    assert "Look for trends, not isolated numbers" in html

    # Designed to fail safely
    assert "Designed to fail safely" in html
    assert "Primary Path" in html
    assert "Active Production ML Model" in html
    assert "Automated Rollback to Prior Validated ML Release Candidate" in html
    assert "Deterministic Rule-Based Engine" in html
    assert "Safe Generic Baseline Guidance" in html


def test_technical_architecture_pipeline_and_auditability(client):
    """Verify technical architecture drawer preserves ML and auditability concepts."""
    res = client.get("/how-it-works")
    html = res.data.decode("utf-8")

    assert "Inside the Vitalis AI Pipeline" in html
    assert "Machine Learning Pipelines" in html
    assert "gradient boosting pipeline" in html
    assert "Isolation Forest algorithms" in html
    assert "Four-Tier Fallback Hierarchy" in html
    assert "Explainability & Auditability" in html
    assert "input feature vectors" in html
    assert "model artifact hash" in html
    assert "confidence calibration" in html

    # Localized ShapeBlur accent mount
    assert 'id="hiw-hero-shapeblur"' in html


def test_clinical_disclaimer_callout(client):
    """Verify presence of clinical disclaimer callout."""
    res = client.get("/how-it-works")
    html = res.data.decode("utf-8")

    assert "Health & Clinical Disclaimer" in html
    assert "does not provide medical advice, diagnosis, or treatment" in html


def test_footer_excluded_on_how_it_works_page(client):
    """Verify that universal site-footer and 'Learn How Vitalis AI Works' link are omitted on /how-it-works."""
    res = client.get("/how-it-works")
    html = res.data.decode("utf-8")

    assert 'id="site-footer"' not in html
    assert "Learn How Vitalis AI Works &rarr;" not in html
    assert "Learn How Vitalis AI Works →" not in html

    # Verify that footer is still present on other pages (e.g. login)
    login_res = client.get("/login")
    login_html = login_res.data.decode("utf-8")
    assert 'id="site-footer"' in login_html


def test_static_assets_served_and_valid(client):
    """Verify how_it_works.css and how_it_works.js are served and contain key styles/logic."""
    css_res = client.get("/static/css/how_it_works.css")
    assert css_res.status_code == 200
    css = css_res.data.decode("utf-8")
    assert ".hiw-container" in css
    assert ".hiw-stack-card" in css
    assert "prefers-reduced-motion" in css
    assert "--mouse-x" in css

    js_res = client.get("/static/js/how_it_works.js")
    assert js_res.status_code == 200
    js = js_res.data.decode("utf-8")
    assert "initScrollReveal" in js
    assert "initSpotlightAndDepthCards" in js
    assert "initScrollStack" in js
    assert "triggerWellnessScoreAnimation" in js
    assert "triggerTrendAnimation" in js
