
import os, sys
sys.path.insert(0, '.')
from dotenv import load_dotenv; load_dotenv()
from pathlib import Path
session_path = Path(os.getenv("WHATSAPP_SESSION_PATH", "credentials/whatsapp_session"))
headless = os.getenv("AGENT_MODE","local") != "local"
print("headless:", headless)
def _check():
    from playwright.sync_api import sync_playwright
    with sync_playwright() as p:
        b = p.chromium.launch_persistent_context(
            user_data_dir=str(session_path), headless=headless,
            args=["--no-sandbox","--disable-dev-shm-usage","--disable-gpu"],
        )
        pg = b.pages[0] if b.pages else b.new_page()
        print("Browser OK")
        b.close()
_check()
print("PASS")
