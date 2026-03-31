#!/usr/bin/env python3
"""
scripts/setup_facebook_session.py — One-time Facebook session setup.

Opens facebook.com/messages in a VISIBLE browser window.
Log in with your Facebook account. The session is saved to
FACEBOOK_SESSION_PATH so subsequent watcher runs work headless.

Usage:
    python scripts/setup_facebook_session.py
"""
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from dotenv import load_dotenv

load_dotenv()

from playwright.sync_api import sync_playwright

SESSION_PATH = Path(os.getenv("FACEBOOK_SESSION_PATH", "credentials/facebook_session"))
SESSION_PATH.mkdir(parents=True, exist_ok=True)

_MESSENGER_URL = "https://www.facebook.com/messages/"
_LOGIN_SEL = 'input#email, input[name="email"]'
# Only selectors that appear AFTER a successful Messenger login (not on the login page)
_LOADED_SEL = '[aria-label="Messenger"], [aria-label="Chats"], [aria-label="New message"]'

print("=" * 60)
print("  Facebook Messenger Session Setup")
print("=" * 60)
print(f"\nSession path: {SESSION_PATH.resolve()}")
print("\nSteps:")
print("  1. A Chrome window will open with facebook.com/messages/.")
print("  2. Log in with your Facebook username and password.")
print("  3. Once Messenger loads, this script saves the session and exits.")
print("  4. Do NOT close the browser manually.\n")

with sync_playwright() as p:
    print("\nOpening Facebook Messenger...")
    ctx = p.chromium.launch_persistent_context(
        user_data_dir=str(SESSION_PATH),
        headless=False,
        args=["--no-sandbox", "--disable-dev-shm-usage", "--disable-gpu"],
        viewport={"width": 1280, "height": 800},
    )
    page = ctx.pages[0] if ctx.pages else ctx.new_page()
    page.goto(_MESSENGER_URL)

    print("Waiting for page to load...")

    # Wait for login form OR messenger to appear
    try:
        page.wait_for_selector(f"{_LOADED_SEL}, {_LOGIN_SEL}", timeout=30_000)
    except Exception:
        pass

    login_form = page.query_selector(_LOGIN_SEL)
    if login_form:
        print("\nLogin form detected. Please log in with your Facebook credentials.")
        print("Waiting up to 5 minutes for you to complete login...\n")
        try:
            page.wait_for_selector(_LOADED_SEL, timeout=300_000)
            print("\nSuccessfully logged in!")
        except Exception:
            print("\nTimed out. Please try again.")
            ctx.close()
            sys.exit(1)
    else:
        messenger = page.query_selector(_LOADED_SEL)
        if messenger:
            print("Already logged in! Session is valid.")
        else:
            print("Waiting for Messenger to load...")
            try:
                page.wait_for_selector(_LOADED_SEL, timeout=300_000)
                print("Logged in!")
            except Exception:
                print("Could not confirm login. Check the browser window.")
                ctx.close()
                sys.exit(1)

    print(f"\nSession saved to: {SESSION_PATH.resolve()}")
    print("Closing browser in 3 seconds...")
    page.wait_for_timeout(3000)
    ctx.close()

print("\nDone! FacebookWatcher will now work in headless mode.")
print("Add FACEBOOK_SESSION_PATH to .env, then run:")
print("  python -m src.watchers.facebook_watcher")
