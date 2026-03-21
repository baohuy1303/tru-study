"""
Brightspace authentication via Playwright SSO.
Logs into learn.truman.edu, captures the Bearer token from outgoing API requests.
"""

import asyncio
import os
from dotenv import load_dotenv
from playwright.async_api import async_playwright

load_dotenv()

BASE_URL = "https://learn.truman.edu"
LOGIN_URL = f"{BASE_URL}/d2l/login"
WHOAMI_URL = f"{BASE_URL}/d2l/api/lp/1.57/users/whoami"


async def get_brightspace_token(username: str, password: str) -> str:
    """
    Opens a browser, logs in via Truman SSO, and returns the Bearer token
    captured from outgoing Brightspace API requests.

    Falls back to returning cookie-based session info if no Bearer token is found.
    """
    captured = {}

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=False)
        context = await browser.new_context()
        page = await context.new_page()

        # Intercept all requests and grab Authorization: Bearer headers
        async def handle_request(request):
            if "token" in captured:
                return
            auth = request.headers.get("authorization", "")
            if auth.startswith("Bearer "):
                captured["token"] = auth[len("Bearer "):]

        page.on("request", handle_request)

        # Step 1: Navigate to Brightspace login
        await page.goto(LOGIN_URL)

        # Step 2: Click the Truman SSO button
        await page.click("button.d2l-button-sso-1")

        # Step 3: Fill in Truman CAS credentials
        await page.wait_for_selector("#username")
        await page.fill("#username", username)
        await page.fill("#password", password)
        await page.click("input[name='_eventId_proceed']")

        # Step 4: Wait for redirect back to Brightspace after SSO
        await page.wait_for_url(f"{BASE_URL}/**", timeout=30000)
        await page.wait_for_load_state("networkidle")

        # Step 5: If no Bearer token captured yet, navigate to a known API endpoint
        # to trigger the browser to send auth headers
        if "token" not in captured:
            await page.goto(WHOAMI_URL)
            await page.wait_for_load_state("networkidle")

        # Step 6: Fallback — extract session cookies if still no Bearer token
        if "token" not in captured:
            cookies = await context.cookies()
            session_cookies = {c["name"]: c["value"] for c in cookies if "d2l" in c["name"].lower()}
            print("[brightspace_auth] No Bearer token found in headers. Session cookies:", list(session_cookies.keys()))
            captured["cookies"] = session_cookies

        await browser.close()

    token = captured.get("token", "")
    if token:
        print(f"[brightspace_auth] Bearer token captured: {token[:20]}...")
    return token


if __name__ == "__main__":
    username = os.getenv("BS_USER", "")
    password = os.getenv("BS_PASS", "")
    if not username or not password:
        print("Set BS_USER and BS_PASS environment variables.")
    else:
        token = asyncio.run(get_brightspace_token(username, password))
        print("Token:", token[:30] if token else "(none captured)")
