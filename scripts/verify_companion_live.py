"""
End-to-End Live Verification Script for:
1. Global Vitalis AI Health Companion on all authenticated pages.
2. User name / profile interactive badge opening /profile.
3. Clean navigation hierarchy without duplicate Profile link.
"""
import urllib.request
import urllib.parse
import http.cookiejar
import json
import sys

BASE_URL = "http://127.0.0.1:5000"

def test_companion_and_profile_live():
    print(f"Connecting to live server at {BASE_URL} ...")
    
    # 1. Test unauthenticated /login does NOT render companion
    with urllib.request.urlopen(f"{BASE_URL}/login") as res:
        assert res.status == 200
        login_html = res.read().decode('utf-8')
        assert 'id="vitalis-companion-root"' not in login_html
        assert 'vitalis-companion-launcher' not in login_html
        assert 'vitalis-companion-panel' not in login_html
        print("PASS 1: Unauthenticated page (/login) does NOT render the AI companion.")

    # 2. Authenticate as Demo user
    cj = http.cookiejar.CookieJar()
    opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(cj))
    login_data = urllib.parse.urlencode({'email': 'demo@wellness.ai', 'password': 'DemoPass123!'}).encode('utf-8')
    req = urllib.request.Request(f"{BASE_URL}/login", data=login_data, method="POST")
    with opener.open(req) as res:
        assert res.status == 200
        dash_html = res.read().decode('utf-8')
        assert 'Alex' in dash_html
        print("PASS 2: Demo user successfully authenticated.")

    # 3. Test companion presence across ALL authenticated pages
    authenticated_pages = [
        ("/dashboard", "Dashboard"),
        ("/activity", "Activity"),
        ("/recommendations", "Recommendations"),
        ("/progress", "Progress"),
        ("/weekly-report", "Weekly Report"),
        ("/assistant", "AI Assistant"),
        ("/profile", "Profile"),
        ("/how-it-works", "How It Works")
    ]

    for path, name in authenticated_pages:
        url = f"{BASE_URL}{path}"
        with opener.open(url) as res:
            assert res.status == 200
            page_html = res.read().decode('utf-8')
            
            # Companion root, launcher, panel, wrapper, and ShapeBlur mount
            assert 'id="vitalis-companion-root"' in page_html, f"Companion root missing on {name}"
            assert 'id="vitalis-companion-launcher"' in page_html, f"Launcher missing on {name}"
            assert 'id="vitalis-companion-panel"' in page_html, f"Panel missing on {name}"
            assert 'id="vitalis-companion-launcher-wrapper"' in page_html, f"Wrapper missing on {name}"
            assert 'id="vitalis-shapeblur-mount"' in page_html, f"ShapeBlur mount missing on {name}"
            assert 'three.min.js' in page_html, f"three.min.js missing on {name}"
            
            # Robot SVG elements
            assert 'class="companion-avatar-icon"' in page_html
            assert 'bot-antenna-stalk' in page_html
            assert 'bot-pulse-line' in page_html
            assert 'bot-eye' in page_html

            # User badge profile control
            assert 'id="current-user-badge"' in page_html
            assert 'href="/profile"' in page_html
            assert 'Alex' in page_html
            
            # Ensure separate Profile link and standalone AI Assistant link are removed from nav menu
            assert 'id="nav-profile"' not in page_html
            assert 'id="nav-assistant"' not in page_html

            print(f"PASS 3: Verified {name} ({path}) has active companion launcher, ShapeBlur mount, and profile badge.")

    # 4. Test companion chat API
    chat_url = f"{BASE_URL}/api/assistant/chat"
    query_payload = json.dumps({"message": "What should I focus on for my wellness today?"}).encode('utf-8')
    chat_req = urllib.request.Request(chat_url, data=query_payload, headers={"Content-Type": "application/json"}, method="POST")
    with opener.open(chat_req) as res:
        assert res.status == 200
        reply_data = json.loads(res.read().decode('utf-8'))
        assert "reply" in reply_data
        assert "disclaimer" in reply_data
        assert len(reply_data["reply"]) > 10
        print(f"PASS 4: Assistant API response verified: '{reply_data['reply'][:60]}...'")

    # 5. Test Profile page functionality & editing
    profile_url = f"{BASE_URL}/profile"
    with opener.open(profile_url) as res:
        assert res.status == 200
        prof_html = res.read().decode('utf-8')
        assert 'Personal Health & Lifestyle Profile' in prof_html
        assert 'Estimated Physiological Metrics' in prof_html
        assert 'Body Mass Index (BMI)' in prof_html
        print("PASS 5: Profile page rendering and biometrics display verified.")

    # 6. Test static CSS has companion, ShapeBlur, and profile rules
    with urllib.request.urlopen(f"{BASE_URL}/static/css/main.css") as res:
        assert res.status == 200
        css = res.read().decode('utf-8')
        assert ".vitalis-companion-launcher" in css
        assert ".vitalis-companion-launcher-wrapper" in css
        assert ".vitalis-shapeblur-mount" in css
        assert ".vitalis-companion-panel" in css
        assert "@keyframes companion-float" in css
        assert "@media (prefers-reduced-motion: reduce)" in css
        assert ".user-badge:hover" in css
        print("PASS 6: main.css served live with ShapeBlur mount, wrapper, companion styles, and reduced-motion support.")

    # 7. Test static JS has VitalisCompanion and VitalisShapeBlur controller
    with urllib.request.urlopen(f"{BASE_URL}/static/js/main.js") as res:
        assert res.status == 200
        js = res.read().decode('utf-8')
        assert "window.VitalisCompanion = VitalisCompanion" in js
        assert "window.VitalisShapeBlur = VitalisShapeBlur" in js
        assert "THREE.MathUtils.damp" in js
        assert "sdRoundRect" in js
        assert "strokeAA" in js
        assert "open()" in js
        assert "close()" in js
        assert "toggle()" in js
        assert "handleSubmit" in js
        print("PASS 7: main.js served live with VitalisCompanion and VitalisShapeBlur WebGL module.")

    # 8. Test static Three.js library is accessible
    with urllib.request.urlopen(f"{BASE_URL}/static/js/three.min.js") as res:
        assert res.status == 200
        three_content = res.read().decode('utf-8', errors='ignore')
        assert "WebGLRenderer" in three_content
        assert "ShaderMaterial" in three_content
        print("PASS 8: three.min.js served live with WebGLRenderer and ShaderMaterial.")

    print("\nALL 8 LIVE COMPANION AND PROFILE VERIFICATIONS PASSED SUCCESSFULLY!")

if __name__ == "__main__":
    test_companion_and_profile_live()
