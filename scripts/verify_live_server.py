import urllib.request
import http.cookiejar
import urllib.parse
import sys

def main():
    print("Testing Live Server at http://127.0.0.1:5000 ...")
    cj = http.cookiejar.CookieJar()
    opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(cj))

    # 1. GET login page
    resp = opener.open('http://127.0.0.1:5000/login')
    assert resp.status == 200, f"Expected 200, got {resp.status}"
    html = resp.read().decode('utf-8')
    assert 'Continue with Google' in html, "Google button missing"
    assert 'id="btn-google-login"' in html, "Google button id missing"
    assert 'Continue with Apple' in html, "Apple button missing"
    assert 'id="btn-apple-login"' in html, "Apple button id missing"
    assert 'Instant Demo Credentials' in html, "Demo section missing"
    assert 'btn-fill-demo' in html, "Demo button missing"
    assert 'btn-fill-admin' in html, "Admin button missing"
    print("PASS 1: Login page layout verified (Google, Apple, Demo, Admin buttons present).")

    # 2. Test Demo Login
    login_data = urllib.parse.urlencode({'email': 'demo@wellness.ai', 'password': 'DemoPass123!'}).encode('utf-8')
    resp = opener.open('http://127.0.0.1:5000/login', data=login_data)
    dash_html = resp.read().decode('utf-8')
    assert 'Alex' in dash_html, "Demo user name missing in dashboard"
    assert 'Wellness Score' in dash_html or 'Dashboard' in dash_html, "Dashboard content missing"
    print("PASS 2: Demo login succeeded (Alex Taylor).")

    # 3. Test Logout
    resp = opener.open('http://127.0.0.1:5000/logout')
    logout_html = resp.read().decode('utf-8')
    assert 'logged out' in logout_html, "Logout message missing"
    print("PASS 3: Logout succeeded and session terminated.")

    # 4. Test Admin Login
    admin_data = urllib.parse.urlencode({'email': 'admin@wellness.ai', 'password': 'AdminPass123!'}).encode('utf-8')
    resp = opener.open('http://127.0.0.1:5000/login', data=admin_data)
    admin_html = resp.read().decode('utf-8')
    assert 'Admin ML' in admin_html, "Admin ML link missing for admin user"
    print("PASS 4: Admin login succeeded (System Administrator).")

    # 5. Logout admin
    opener.open('http://127.0.0.1:5000/logout')

    # 6. Test OAuth Direct Redirection (No warning banners, direct redirect to Google and Apple)
    class NoRedirectHandler(urllib.request.HTTPRedirectHandler):
        def http_error_302(self, req, fp, code, msg, headers):
            return fp

    no_redirect_opener = urllib.request.build_opener(NoRedirectHandler)

    req_google = urllib.request.Request('http://127.0.0.1:5000/auth/google')
    try:
        resp_google = no_redirect_opener.open(req_google)
        loc = resp_google.headers.get('Location', '')
    except urllib.error.HTTPError as e:
        loc = e.headers.get('Location', '')

    assert 'accounts.google.com' in loc, f"Expected redirect to accounts.google.com, got: {loc}"
    assert 'prompt=select_account' in loc, f"Expected prompt=select_account in {loc}"
    assert 'login_hint' not in loc, f"login_hint must not be present, got: {loc}"
    assert 'hd=' not in loc, f"hd domain restriction must not be present, got: {loc}"
    assert 'client_id=30911211040-qnum270temss1avpsqbk0r9fvq73qinl.apps.googleusercontent.com' in loc
    assert 'redirect_uri=http%3A%2F%2F127.0.0.1%3A5000%2Fauth%2Fgoogle%2Fcallback' in loc
    print("PASS 5: Google auth route correctly redirects to Google accounts chooser with prompt=select_account and no login_hint or hd.")

    resp_apple = opener.open('http://127.0.0.1:5000/auth/apple')
    apple_html = resp_apple.read().decode('utf-8')
    assert 'Apple sign-in is not yet configured' in apple_html
    print("PASS 6: Apple auth route gracefully handles unconfigured credentials.")

    print("\nALL LIVE SERVER END-TO-END HTTP TESTS PASSED!")

if __name__ == "__main__":
    main()
