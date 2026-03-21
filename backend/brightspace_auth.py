"""
Brightspace authentication via Playwright SSO.
Logs into learn.truman.edu, captures the Bearer token from outgoing API requests.

Uses sync_playwright in a thread to avoid Windows event loop issues with uvicorn.
"""

import asyncio
import os
from concurrent.futures import ThreadPoolExecutor
from dotenv import load_dotenv
from playwright.sync_api import sync_playwright

load_dotenv()

BASE_URL = "https://learn.truman.edu"
LOGIN_URL = f"{BASE_URL}/d2l/login"
WHOAMI_URL = f"{BASE_URL}/d2l/api/lp/1.57/users/whoami"

_executor = ThreadPoolExecutor(max_workers=2)


def _run_playwright_login(username: str, password: str) -> str:
    """Sync function that runs Playwright in its own thread (avoids uvicorn event loop issues)."""
    captured = {}

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False)
        context = browser.new_context()
        page = context.new_page()

        # Intercept all requests and grab Authorization: Bearer headers
        def handle_request(request):
            if "token" in captured:
                return
            auth = request.headers.get("authorization", "")
            if auth.startswith("Bearer "):
                captured["token"] = auth[len("Bearer "):]

        page.on("request", handle_request)

        # Step 1: Navigate to Brightspace login
        page.goto(LOGIN_URL)

        # Step 2: Click the Truman SSO button
        page.click("button.d2l-button-sso-1")

        # Step 3: Fill in Truman CAS credentials
        page.wait_for_selector("#username")
        page.fill("#username", username)
        page.fill("#password", password)
        page.click("input[name='_eventId_proceed']")

        # Step 4: Wait for redirect back to Brightspace after SSO
        page.wait_for_url(f"{BASE_URL}/**", timeout=30000)
        page.wait_for_load_state("networkidle")

        # Step 5: If no Bearer token captured yet, navigate to a known API endpoint
        if "token" not in captured:
            page.goto(WHOAMI_URL)
            page.wait_for_load_state("networkidle")

        # Step 6: Fallback — extract session cookies if still no Bearer token
        if "token" not in captured:
            cookies = context.cookies()
            session_cookies = {c["name"]: c["value"] for c in cookies if "d2l" in c["name"].lower()}
            print("[brightspace_auth] No Bearer token found in headers. Session cookies:", list(session_cookies.keys()))
            captured["cookies"] = session_cookies

        browser.close()

    token = captured.get("token", "")
    if token:
        print(f"[brightspace_auth] Bearer token captured: {token[:20]}...")
    return token


async def get_brightspace_token(username: str, password: str) -> str:
    """Async wrapper — runs Playwright login in a thread pool to avoid event loop conflicts."""
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(_executor, _run_playwright_login, username, password)


if __name__ == "__main__":
    username = os.getenv("BS_USER", "")
    password = os.getenv("BS_PASS", "")
    if not username or not password:
        print("Set BS_USER and BS_PASS environment variables.")
    else:
        token = asyncio.run(get_brightspace_token(username, password))
        print("Token:", token[:30] if token else "(none captured)")
