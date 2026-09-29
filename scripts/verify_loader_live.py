"""
Verification script for the minimal Vitalis loading animation on live server.
Tests live responses, assets, DOM inclusion, CSS rules, JS navigation hooks, and API.
"""
import urllib.request
import urllib.parse
import http.cookiejar
import re
import sys

BASE_URL = "http://127.0.0.1:5000"

def test_loader_live():
    print(f"Connecting to live server at {BASE_URL} ...")
    
    # 1. Test static CSS has vitalis loader rules
    css_url = f"{BASE_URL}/static/css/main.css"
    with urllib.request.urlopen(css_url) as res:
        assert res.status == 200
        css = res.read().decode('utf-8')
        assert ".vitalis-loading-pulse" in css
        assert "stroke: #ffffff" in css
        assert "vitalis-pulse-loading 0.9s ease-in-out infinite" in css
        assert "@keyframes vitalis-pulse-loading" in css
        assert "@media (prefers-reduced-motion: reduce)" in css
        assert "background: transparent !important" in css
        assert "opacity 100ms" in css
        assert "opacity 120ms" in css
        print("PASS 1: main.css served live with transparent background, 100ms/120ms transitions, and 0.9s animation.")

    # 2. Test static JS has VitalisLoader module with immediate navigation and rAF
    js_url = f"{BASE_URL}/static/js/main.js"
    with urllib.request.urlopen(js_url) as res:
        assert res.status == 200
        js = res.read().decode('utf-8')
        assert "window.VitalisLoader = VitalisLoader" in js
        assert "M2 12h4l3-9 6 18 3-9h4" in js
        assert "getSvgString" in js
        assert "setButtonLoading" in js
        assert "showOverlay" in js
        assert "hideOverlay" in js
        assert "triggerNavigation" in js
        assert "isNavigationalLink" in js
        assert "requestAnimationFrame" in js
        assert "switchTab" in js
        print("PASS 2: main.js served live with immediate navigation triggering, rAF paint guarantee, and switchTab API.")

    # 3. Test login page HTML includes the global overlay with exact pulse SVG
    login_url = f"{BASE_URL}/login"
    with urllib.request.urlopen(login_url) as res:
        assert res.status == 200
        html = res.read().decode('utf-8')
        assert 'id="vitalis-global-overlay"' in html
        assert 'vitalis-loader-overlay' in html
        assert 'vitalis-loader-svg' in html
        assert 'vitalis-loading-pulse' in html
        assert 'M2 12h4l3-9 6 18 3-9h4' in html
        assert 'pathLength="100"' in html
        print("PASS 3: /login renders global vitalis minimal overlay with exact path geometry.")

    # 4. Test authenticated session & dashboard navigation tabs
    cj = http.cookiejar.CookieJar()
    opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(cj))
    
    # Demo login
    login_data = urllib.parse.urlencode({'email': 'demo@wellness.ai', 'password': 'DemoPass123!'}).encode('utf-8')
    req = urllib.request.Request(f"{BASE_URL}/login", data=login_data, method="POST")
    with opener.open(req) as res:
        assert res.status == 200
        dash_html = res.read().decode('utf-8')
        assert 'id="vitalis-global-overlay"' in dash_html
        
        # Verify primary navigation links and profile user badge
        expected_nav_links = [
            'id="nav-dashboard"',
            'id="nav-activity"',
            'id="nav-recommendations"',
            'id="nav-progress"',
            'id="nav-weekly-report"',
            'id="nav-assistant"',
            'id="nav-how-it-works"'
        ]
        for nav_id in expected_nav_links:
            assert nav_id in dash_html, f"Navigation link {nav_id} missing in dashboard"
        
        # Verify user badge links to profile and companion is present
        assert 'id="current-user-badge"' in dash_html
        assert 'href="/profile"' in dash_html
        assert 'id="vitalis-companion-launcher"' in dash_html
        print("PASS 4: Demo login successful, primary navigation verified, user-badge profile link verified, and companion launcher active.")

    # 5. Assistant page has VitalisLoader integration
    assistant_url = f"{BASE_URL}/assistant"
    with opener.open(assistant_url) as res:
        assert res.status == 200
        assist_html = res.read().decode('utf-8')
        assert 'VitalisLoader.inlineHtml' in assist_html
        assert 'VitalisLoader.setButtonLoading' in assist_html
        print("PASS 5: /assistant template verified with VitalisLoader in chat streaming.")

    # 6. Assistant chat API works live
    chat_api_url = f"{BASE_URL}/api/assistant/chat"
    chat_payload = b'{"message":"How is my wellness score calculated?"}'
    chat_req = urllib.request.Request(
        chat_api_url, 
        data=chat_payload, 
        headers={"Content-Type": "application/json"},
        method="POST"
    )
    with opener.open(chat_req) as res:
        assert res.status == 200
        data = res.read().decode('utf-8')
        assert "reply" in data
        print("PASS 6: /api/assistant/chat responds successfully.")

    # 7. Progress page range selectors
    progress_url = f"{BASE_URL}/progress"
    with opener.open(progress_url) as res:
        assert res.status == 200
        prog_html = res.read().decode('utf-8')
        assert 'href="/progress?days=7"' in prog_html or 'days=7' in prog_html
        print("PASS 7: Progress trends range links verified.")

    print("\nALL LIVE LOADER AND NAVIGATION VERIFICATIONS PASSED SUCCESSFULLY!")

if __name__ == "__main__":
    test_loader_live()
