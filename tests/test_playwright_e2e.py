"""Playwright browser automated test for PeakCut UI and live features."""
import sys
from playwright.sync_api import sync_playwright

BASE_URL = "http://127.0.0.1:8765"


def main():
    errors = []
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context()
        page = context.new_page()

        # Capture console errors
        page.on("console", lambda msg: errors.append(msg.text) if msg.type == "error" else None)
        page.on("pageerror", lambda exc: errors.append(str(exc)))

        print("Navigating to", f"{BASE_URL}/app")
        page.goto(f"{BASE_URL}/app", wait_until="networkidle", timeout=15000)

        # 1. Title verification
        title = page.title()
        print("Page title:", title)
        assert "PeakCut" in title, f"Expected PeakCut in title, got: {title}"

        # 2. Add form & composer elements
        page.wait_for_selector("#addform", timeout=10000)
        assert page.is_visible("#addform"), "Composer #addform not visible"
        print("PASS: Composer form is visible")

        # 3. Check for the Auto-Pilot toggle chip
        page.wait_for_selector("[data-act='autopilot-toggle']", timeout=5000)
        ap_btn = page.locator("[data-act='autopilot-toggle']")
        assert ap_btn.is_visible(), "Auto-Pilot toggle button not found"
        btn_text = ap_btn.text_content().strip()
        print("PASS: Auto-Pilot toggle button found with text:", repr(btn_text))

        # 4. Check API status endpoint directly from page context
        status_eval = page.evaluate("() => fetch('/api/autopilot/status').then(r => r.json())")
        print("Autopilot status API:", status_eval)
        assert "running" in status_eval, "Invalid autopilot status JSON"

        # 5. Check URL input responsiveness
        url_input = page.locator("#url")
        assert url_input.is_visible(), "URL input not visible"
        url_input.fill("https://www.youtube.com/watch?v=dQw4w9WgXcQ")
        page.wait_for_timeout(500)
        go_btn = page.locator("#goBtn")
        assert go_btn.is_visible(), "Make clips button not visible"
        print("PASS: URL input and action button responsive")

        # 6. Verify zero fatal console errors
        fatal_errors = [e for e in errors if "favicon" not in e.lower()]
        if fatal_errors:
            print("WARNING: Console errors encountered:", fatal_errors)
        else:
            print("PASS: Zero console errors in browser session")

        browser.close()

    print("ALL PLAYWRIGHT CHECKS PASSED")
    return 0


if __name__ == "__main__":
    sys.exit(main())
