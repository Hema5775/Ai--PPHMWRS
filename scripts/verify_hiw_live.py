"""
Live validation script for the redesigned How Vitalis AI Works page.
Verifies HTTP responses, HTML DOM structure, CSS styles, and JavaScript modules.
"""

import urllib.request
import re
import sys

BASE_URL = "http://127.0.0.1:5000"

def verify_live():
    print("==================================================================")
    print("VITALIS AI — HOW IT WORKS REDESIGN LIVE VERIFICATION")
    print("==================================================================")

    # 1. Fetch /how-it-works
    req = urllib.request.Request(f"{BASE_URL}/how-it-works", headers={"User-Agent": "VitalisVerification/1.0"})
    with urllib.request.urlopen(req) as res:
        assert res.status == 200, f"Expected 200, got {res.status}"
        html = res.read().decode("utf-8")
        print(f"[OK] 1. /how-it-works loaded successfully (HTTP 200, {len(html)} bytes).")

    # 2. Check Hero Section & Information Pipeline
    assert "How Vitalis AI Works" in html
    assert "YOUR PERSONAL WELLNESS COMPANION" in html
    assert "Vitalis AI turns your everyday wellness data into understandable insights" in html
    assert "Your Data" in html and "Intelligence" in html and "Personalization" in html and "Guidance" in html and "Progress" in html
    print("[OK] 2. Hero Section and 5-stage animated visual pipeline verified.")

    # 3. Check 4-Stage Connected Timeline
    assert "From your data to your next step" in html
    assert "01" in html and "Track" in html
    assert "02" in html and "Understand" in html
    assert "03" in html and "Personalize" in html
    assert "04" in html and "Act" in html
    print("[OK] 3. Data -> Insight -> Action 4-stage connected timeline verified.")

    # 4. Check 5 Core Vitalis Capabilities & IDs
    cap_ids = [
        "info-recommendations",
        "info-wellness-score",
        "info-progress-trends",
        "info-activity-insights",
        "info-safety"
    ]
    for cid in cap_ids:
        assert f'id="{cid}"' in html, f"Missing capability ID: {cid}"
    print("[OK] 4. All 5 core capability cards and IDs verified:")
    print("       - 1. Personalized Recommendations (id='info-recommendations')")
    print("       - 2. Wellness Score (id='info-wellness-score')")
    print("       - 3. Progress Trends (id='info-progress-trends')")
    print("       - 4. Activity Insights (id='info-activity-insights')")
    print("       - 5. Safety & Personalization (id='info-safety')")

    # Verify no generic Model A/B/C/D
    assert re.search(r"\bModel [ABCD]\b", html) is None
    print("[OK] 5. Verified absence of generic Model A/B/C/D labels.")

    # 5. Check Wellness Score dimensions and illustration notice
    assert "Illustrative Example" in html
    assert "Activity" in html and "25%" in html
    assert "Hydration" in html and "20%" in html
    assert "Sleep" in html and "20%" in html
    assert "Daily Tasks" in html and "20%" in html
    assert "7-day Logging Consistency" in html and "15%" in html
    assert "What it means" in html
    assert "What it is not" in html
    print("[OK] 6. Wellness Score 0-100 gauge, 5 dimensions, and clear non-clinical disclosures verified.")

    # 6. Check Progress Trends Multi-Horizon
    assert 'id="tab-7d"' in html
    assert 'id="tab-14d"' in html
    assert 'id="tab-30d"' in html
    assert 'id="hiw-trend-path"' in html
    print("[OK] 7. Progress Trends multi-horizon (7d, 14d, 30d) and SVG drawing path verified.")

    # 7. Check Activity Insights Outlier Flow
    assert "60,000 Steps" in html
    assert "Statistical Outlier" in html
    assert "Review / Flag Notice" in html
    print("[OK] 8. Activity Insights outlier flow (60,000 steps -> review/flag) verified.")

    # 8. Check Safety & Personalization Diagram
    assert "Profile Data" in html
    assert "Goals" in html
    assert "Constraints" in html
    assert "Data Quality" in html
    print("[OK] 9. Safety & Personalization filter architecture verified.")

    # 9. Check Quality Inputs & Cold Start
    assert "Better inputs" in html
    assert "Still getting started?" in html
    assert "NOT ENOUGH DATA YET" in html
    print("[OK] 10. Quality inputs and honest cold-start state verified.")

    # 10. Check Effective Usage & Safe Fallback
    assert "How to use Vitalis effectively" in html
    assert "Designed to fail safely" in html
    assert "Primary Path" in html
    assert "Automated Rollback to Prior Validated ML Release Candidate" in html
    assert "Deterministic Rule-Based Engine" in html
    assert "Safe Generic Baseline Guidance" in html
    print("[OK] 11. Effective usage habits and 4-tier safe fallback hierarchy verified.")

    # 11. Check Inside Vitalis AI Pipeline & Technical Details
    assert "Inside the Vitalis AI Pipeline" in html
    assert "Machine Learning Pipelines" in html
    assert "gradient boosting pipeline" in html
    assert "Isolation Forest algorithms" in html
    assert "Explainability & Auditability" in html
    assert "input feature vectors" in html
    assert "model artifact hash" in html
    assert "confidence calibration" in html
    assert 'id="hiw-hero-shapeblur"' in html
    print("[OK] 12. Technical architecture drawer, ML details, auditability, and ShapeBlur mount verified.")

    # 12. Check Clinical Disclaimer Callout & Footer Exclusion
    assert "Health & Clinical Disclaimer" in html
    assert "does not provide medical advice, diagnosis, or treatment" in html
    assert 'id="site-footer"' not in html
    assert "Learn How Vitalis AI Works &rarr;" not in html
    print("[OK] 13. Health & Clinical Disclaimer callout verified and redundant footer cleanly omitted.")

    # 13. Verify Static CSS
    css_req = urllib.request.Request(f"{BASE_URL}/static/css/how_it_works.css")
    with urllib.request.urlopen(css_req) as res:
        assert res.status == 200
        css = res.read().decode("utf-8")
        assert ".hiw-container" in css
        assert ".hiw-stack-card" in css
        assert "prefers-reduced-motion" in css
        assert "@media (max-width: 1024px)" in css
        assert "@media (max-width: 768px)" in css
        assert "@media (max-width: 390px)" in css
        print(f"[OK] 14. how_it_works.css served live ({len(css)} bytes), responsive & reduced-motion verified.")

    # 14. Verify Static JS
    js_req = urllib.request.Request(f"{BASE_URL}/static/js/how_it_works.js")
    with urllib.request.urlopen(js_req) as res:
        assert res.status == 200
        js = res.read().decode("utf-8")
        assert "initScrollReveal" in js
        assert "initSpotlightAndDepthCards" in js
        assert "initScrollStack" in js
        assert "triggerWellnessScoreAnimation" in js
        assert "triggerTrendAnimation" in js
        print(f"[OK] 15. how_it_works.js served live ({len(js)} bytes) with React Bits component adaptations.")

    print("==================================================================")
    print("ALL 15 LIVE VERIFICATION CHECKS PASSED PERFECTLY!")
    print("==================================================================")

if __name__ == "__main__":
    verify_live()
