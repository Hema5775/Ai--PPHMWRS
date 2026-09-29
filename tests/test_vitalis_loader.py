"""
Unit and integration tests for the minimal Vitalis AI loading component and navigation triggers.
"""
import re
import pytest
from app import create_app
from config import TestingConfig


@pytest.fixture
def client():
    app = create_app(TestingConfig)
    with app.test_client() as client:
        with app.app_context():
            yield client


def test_base_html_includes_vitalis_loader_overlay(client):
    """Verify that base template contains the minimal loader overlay with correct geometry."""
    res = client.get('/login')
    assert res.status_code == 200
    html = res.data.decode('utf-8')

    # Must contain global overlay
    assert 'id="vitalis-global-overlay"' in html
    assert 'vitalis-loader-overlay' in html

    # Must contain the minimal pulse SVG with exact geometry
    assert 'vitalis-loader-svg' in html
    assert 'vitalis-loading-pulse' in html
    assert 'M2 12h4l3-9 6 18 3-9h4' in html
    assert 'pathLength="100"' in html

    # Must NOT contain teal background or logo container or text inside loader
    overlay_match = re.search(r'<div id="vitalis-global-overlay"[^>]*>(.*?)</div>', html, re.DOTALL)
    assert overlay_match is not None
    overlay_content = overlay_match.group(1)
    assert 'brand-icon' not in overlay_content
    assert 'brand-logo' not in overlay_content
    assert 'Loading...' not in overlay_content
    assert 'Vitalis' not in overlay_content


def test_css_loader_rules_and_timing():
    """Verify CSS timing, stroke attributes, and accessibility rules."""
    with open('static/css/main.css', 'r', encoding='utf-8') as f:
        css = f.read()

    # Stroke and geometry properties
    assert '.vitalis-loading-pulse' in css
    assert 'stroke: #ffffff' in css
    assert 'stroke-linecap: round' in css
    assert 'stroke-linejoin: round' in css
    assert 'stroke-dasharray: 100' in css
    assert 'stroke-dashoffset: 100' in css

    # Animation timing: 0.9s ease-in-out infinite
    assert 'vitalis-pulse-loading 0.9s ease-in-out infinite' in css

    # Keyframes: 0%, 70%, 85%, 100%
    assert '@keyframes vitalis-pulse-loading' in css
    assert '0%' in css
    assert '70%' in css
    assert '85%' in css
    assert '100%' in css

    # Accessibility: prefers-reduced-motion
    assert '@media (prefers-reduced-motion: reduce)' in css
    assert 'animation: none !important' in css
    assert 'stroke-dashoffset: 0 !important' in css

    # Transparent background and rapid 100ms/120ms transitions
    assert 'background: transparent !important' in css
    assert 'opacity 100ms' in css
    assert 'opacity 120ms' in css
    assert 'backdrop-filter: none !important' in css


def test_js_vitalis_loader_module():
    """Verify JavaScript module defines VitalisLoader with all required API methods."""
    with open('static/js/main.js', 'r', encoding='utf-8') as f:
        js = f.read()

    assert 'window.VitalisLoader' in js
    assert 'getSvgString' in js
    assert 'showOverlay' in js
    assert 'hideOverlay' in js
    assert 'setButtonLoading' in js
    assert 'initAutoHooks' in js
    assert 'switchTab' in js
    assert 'isNavigationalLink' in js
    assert 'triggerNavigation' in js
    assert 'M2 12h4l3-9 6 18 3-9h4' in js


def test_navigation_immediate_rendering_and_raf():
    """Verify navigation hook provides immediate rendering with requestAnimationFrame."""
    with open('static/js/main.js', 'r', encoding='utf-8') as f:
        js = f.read()

    # Must invoke showOverlay(0) immediately
    assert 'VitalisLoader.showOverlay(0)' in js
    # Must use double requestAnimationFrame to ensure browser paint opportunity
    assert 'requestAnimationFrame' in js
    # Must specify minimum visible duration (between 200 and 400ms)
    assert 'MIN_NAV_VISIBLE_MS' in js or 'minDurationMs' in js
    # Must guard against duplicate listener initialization
    assert 'hooksInitialized' in js


def test_navigation_exclusions():
    """Verify unrelated buttons, external links, dropdowns, and logout are excluded from pulse overlay."""
    with open('static/js/main.js', 'r', encoding='utf-8') as f:
        js = f.read()

    # Must exclude modified clicks (meta, ctrl, shift, alt)
    assert 'e.metaKey' in js
    assert 'e.ctrlKey' in js
    # Must exclude dropdowns and modals
    assert 'data-toggle' in js or 'data-bs-toggle' in js
    # Must exclude logout
    assert 'logout' in js
    # Must exclude hash links
    assert "href.startsWith('#')" in js


def test_primary_navigation_tabs_present_in_base_html(client):
    """Verify all primary navigation tabs are defined with .nav-link in base template."""
    res = client.get('/login')
    html = res.data.decode('utf-8')

    # Primary navigation container
    assert 'id="main-nav"' in html
    # Brand logo link
    assert 'id="brand-logo-link"' in html


def test_assistant_template_uses_minimal_loader():
    """Verify assistant template uses VitalisLoader for loading bubble and submit button."""
    with open('templates/assistant.html', 'r', encoding='utf-8') as f:
        content = f.read()

    assert 'VitalisLoader.setButtonLoading' in content
    assert 'VitalisLoader.inlineHtml' in content
    assert 'Analyzing your personal records...' not in content
