#!/usr/bin/env python3
"""
scripts/setup_whatsapp_session.py — One-time WhatsApp Web session setup.

Opens WhatsApp Web in a VISIBLE browser window. Scan the QR code with your
phone (WhatsApp -> Linked Devices -> Link a Device). The session is saved to
WHATSAPP_SESSION_PATH so subsequent watcher runs work headless.

Usage:
    python scripts/setup_whatsapp_session.py
"""
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from dotenv import load_dotenv

load_dotenv()

from playwright.sync_api import sync_playwright

SESSION_PATH = Path(os.getenv("WHATSAPP_SESSION_PATH", "credentials/whatsapp_session"))
SESSION_PATH.mkdir(parents=True, exist_ok=True)

print("=" * 60)
print("  WhatsApp Web Session Setup")
print("=" * 60)
print(f"\nSession path: {SESSION_PATH.resolve()}")
print("\nSteps:")
print("  1. A Chrome window will open with WhatsApp Web.")
print("  2. On your phone: WhatsApp > Linked Devices > Link a Device.")
print("  3. Scan the QR code in the browser.")
print("  4. Once chat list loads, this script will confirm and exit.")
print("  5. Do NOT close the browser manually.\n")
input("Press Enter to open the browser...")

with sync_playwright() as p:
    print("\nOpening WhatsApp Web...")
    ctx = p.chromium.launch_persistent_context(
        user_data_dir=str(SESSION_PATH),
        headless=False,
        args=["--no-sandbox", "--disable-dev-shm-usage", "--disable-gpu"],
        viewport={"width": 1280, "height": 800},
    )
    page = ctx.pages[0] if ctx.pages else ctx.new_page()
    page.goto("https://web.whatsapp.com")

    print("Waiting for QR code or existing session...")
    print("(You have 3 minutes to scan the QR code)\n")

    _CHAT_SEL = '[aria-label="Chat list"], [data-testid="chat-list"]'
    _QR_SEL = '[data-testid="qrcode"], canvas[aria-label*="QR"], div[data-ref]'

    try:
        # Wait for either the chat list (logged in) or QR code
        page.wait_for_selector(
            f'{_CHAT_SEL}, {_QR_SEL}',
            timeout=30_000,
        )
    except Exception:
        pass

    # Check if QR code needs to be scanned
    qr = (page.query_selector('[data-testid="qrcode"]')
          or page.query_selector('canvas[aria-label*="QR"]')
          or page.query_selector('div[data-ref]'))

    if qr:
        print("QR code detected! Please scan it with your phone now.")
        print("Waiting up to 3 minutes for you to scan...")

        try:
            page.wait_for_selector(_CHAT_SEL, timeout=180_000)
            print("\nSuccessfully logged in!")
        except Exception:
            print("\nTimed out waiting for login. Please try again.")
            ctx.close()
            sys.exit(1)
    else:
        # Check if already logged in
        chat_list = page.query_selector('[aria-label="Chat list"]') or page.query_selector('[data-testid="chat-list"]')
        if chat_list:
            print("Already logged in! Session is valid.")
        else:
            print("Waiting for WhatsApp to load (may need QR scan)...")
            try:
                page.wait_for_selector(_CHAT_SEL, timeout=180_000)
                print("Logged in!")
            except Exception:
                print("Could not confirm login. Check the browser window.")
                ctx.close()
                sys.exit(1)

    print("\nSession saved to:", SESSION_PATH.resolve())
    print("Closing browser in 3 seconds...")
    page.wait_for_timeout(3000)
    ctx.close()

print("\nDone! WhatsApp watcher will now work in headless mode.")
print("Run the watcher with: python -m src.watchers.whatsapp_watcher")
