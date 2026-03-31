#!/usr/bin/env python3
"""
scripts/setup_instagram_session.py — One-time Instagram session setup.

Opens instagram.com in a VISIBLE browser window.
Log in with your Instagram account. The session is saved to
INSTAGRAM_SESSION_PATH so subsequent watcher runs work headless.

Usage:
    python scripts/setup_instagram_session.py
"""
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from dotenv import load_dotenv

load_dotenv()

from playwright.sync_api import sync_playwright

SESSION_PATH = Path(os.getenv("INSTAGRAM_SESSION_PATH", "credentials/instagram_session"))
SESSION_PATH.mkdir(parents=True, exist_ok=True)

_IG_URL = "https://www.instagram.com/"
_DM_URL = "https://www.instagram.com/direct/inbox/"
_LOGIN_SEL = '[aria-label="Phone number, username, or email"], input[name="username"]'
_LOADED_SEL = '[aria-label="Home"], [aria-label="Direct messaging"], svg[aria-label="Home"]'

print("=" * 60)
print("  Instagram Session Setup")
print("=" * 60)
print(f"\nSession path: {SESSION_PATH.resolve()}")
print("\nSteps:")
print("  1. A Chrome window will open with instagram.com.")
print("  2. Log in with your Instagram username and password.")
print("  3. Complete any 2FA if prompted.")
print("  4. Once the home feed loads, this script saves the session and exits.")
print("  5. Do NOT close the browser manually.\n")

with sync_playwright() as p:
    print("\nOpening Instagram...")
    ctx = p.chromium.launch_persistent_context(
        user_data_dir=str(SESSION_PATH),
        headless=False,
        args=["--no-sandbox", "--disable-dev-shm-usage", "--disable-gpu"],
        viewport={"width": 1280, "height": 800},
    )
    page = ctx.pages[0] if ctx.pages else ctx.new_page()
    page.goto(_IG_URL)

    print("Waiting for page to load...")

    try:
        page.wait_for_selector(f"{_LOADED_SEL}, {_LOGIN_SEL}", timeout=30_000)
    except Exception:
        pass

    login_form = page.query_selector(_LOGIN_SEL)
    if login_form:
        print("\nLogin form detected. Please log in with your Instagram credentials.")
        print("Waiting up to 5 minutes for you to complete login...\n")
        try:
            page.wait_for_selector(_LOADED_SEL, timeout=300_000)
            print("\nSuccessfully logged in!")
        except Exception:
            print("\nTimed out. Please try again.")
            ctx.close()
            sys.exit(1)
    else:
        home = page.query_selector(_LOADED_SEL)
        if home:
            print("Already logged in! Session is valid.")
        else:
            print("Waiting for Instagram to load...")
            try:
                page.wait_for_selector(_LOADED_SEL, timeout=300_000)
                print("Logged in!")
            except Exception:
                print("Could not confirm login. Check the browser window.")
                ctx.close()
                sys.exit(1)

    # Navigate to DM inbox to confirm DM access works
    print("Verifying DM inbox access...")
    try:
        page.goto(_DM_URL, timeout=30_000)
        page.wait_for_timeout(2000)
        dm_ok = page.query_selector(
            '[aria-label="Direct messaging"], [role="listbox"], [role="list"]'
        )
        if dm_ok:
            print("DM inbox accessible.")
        else:
            print("DM inbox loaded (no unread DMs visible).")
    except Exception:
        print("DM inbox check skipped — session still saved.")

    print(f"\nSession saved to: {SESSION_PATH.resolve()}")
    print("Closing browser in 3 seconds...")
    page.wait_for_timeout(3000)
    ctx.close()

print("\nDone! InstagramWatcher will now work in headless mode.")
print("Add INSTAGRAM_SESSION_PATH to .env, then run:")
print("  python -m src.watchers.instagram_watcher")
