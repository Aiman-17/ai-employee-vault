"""
src/watchers/facebook_watcher.py — Facebook Messenger perception layer.

Uses Playwright (headless Chromium) with a persistent session to monitor
Facebook Messenger for unread messages containing business keywords.
No access tokens required — just a saved browser login session.

⚠️  Meta Terms of Service: Automation of facebook.com is technically against
    Meta's ToS.  Use only for personal productivity on your own account and
    comply with applicable laws.  Do not use for bulk operations.

Prerequisites:
    pip install playwright
    playwright install chromium

Environment variables:
    FACEBOOK_SESSION_PATH   Directory where Playwright saves the browser session.
                            Persist between runs to avoid re-logging in.
    FACEBOOK_KEYWORDS       Comma-separated keywords to filter messages (default below).
    VAULT_PATH              Obsidian vault root.

Authentication flow:
    1. First run: run scripts/setup_facebook_session.py — log in manually.
    2. Subsequent runs: session reloaded headlessly from FACEBOOK_SESSION_PATH.
    3. If session expires: SessionInvalidError → error card in Needs_Action/.

Selector notes:
    Facebook's UI uses obfuscated CSS class names that change frequently.
    This watcher uses aria-label and role attributes which are more stable.
    If selectors break after a Facebook UI update, open the page in devtools
    and search for aria-label="Messenger" or role="listitem" to find new ones.
"""

import hashlib
import logging
import os
import time
from pathlib import Path

from dotenv import load_dotenv

from src.exceptions import AuthExpiredError, NetworkError, ParseError, SessionInvalidError
from src.watchers.base_watcher import BaseWatcher

load_dotenv()

logger = logging.getLogger(__name__)

_DEFAULT_KEYWORDS = [
    "urgent",
    "asap",
    "invoice",
    "payment",
    "help",
    "deadline",
    "meeting",
    "contract",
    "quote",
    "proposal",
    "price",
    "order",
]

_MESSENGER_URL = "https://www.facebook.com/messages/"
_PAGE_LOAD_TIMEOUT = 60_000  # ms

# ── Selector constants (aria-label based — more stable than class names) ──────
# Login form indicators (if present → not logged in)
_LOGIN_SELECTORS = 'input#email, input[name="email"], [data-testid="royal_login_form"]'

# Messenger loaded indicator — must NOT match the login page (avoid [role="main"])
_MESSENGER_LOADED = (
    '[aria-label="Messenger"], '
    '[aria-label="Chats"], '
    '[aria-label="New message"]'
)

# Conversation rows in the sidebar — unread ones carry aria-label like
# "Sender Name 2 unread messages" or "Sender Name unread message"
_UNREAD_CONV_PATTERN = "unread"  # substring match against conversation aria-labels


class FacebookWatcher(BaseWatcher):
    """
    Browser-based watcher: monitors Facebook Messenger for keyword messages.

    No API token required — uses a saved Playwright browser session.

    Environment variables:
        FACEBOOK_SESSION_PATH   Path to Playwright persistent context directory.
        FACEBOOK_KEYWORDS       Comma-separated list of trigger keywords.
        VAULT_PATH              Obsidian vault root.
    """

    def __init__(self, check_interval: int = 60):
        super().__init__(check_interval=check_interval)

        session_dir = os.getenv("FACEBOOK_SESSION_PATH", "credentials/facebook_session")
        self.session_path = Path(session_dir)

        raw_keywords = os.getenv("FACEBOOK_KEYWORDS", "")
        self.keywords = (
            [k.strip().lower() for k in raw_keywords.split(",") if k.strip()]
            if raw_keywords
            else _DEFAULT_KEYWORDS
        )

        logger.info(
            "FacebookWatcher configured — keywords: %s, session: %s",
            self.keywords,
            self.session_path,
        )

    # ── BaseWatcher interface ─────────────────────────────────────────────────

    def check_for_updates(self) -> list:
        """
        Open Facebook Messenger, find unread conversations with keyword matches.
        Returns a list of dicts with keys: sender, preview, timestamp.
        """
        try:
            from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeout
        except ImportError as exc:
            raise AuthExpiredError(
                f"Playwright not installed: {exc}",
                user_message="Facebook monitoring requires Playwright.",
                action_hint="Run: pip install playwright && playwright install chromium",
            ) from exc

        self.session_path.mkdir(parents=True, exist_ok=True)
        headless = os.getenv("AGENT_MODE", "local") != "local"

        messages = []
        try:
            with sync_playwright() as p:
                browser = p.chromium.launch_persistent_context(
                    user_data_dir=str(self.session_path),
                    headless=headless,
                    args=["--no-sandbox", "--disable-dev-shm-usage", "--disable-gpu"],
                )
                page = browser.pages[0] if browser.pages else browser.new_page()

                try:
                    page.goto(_MESSENGER_URL, timeout=_PAGE_LOAD_TIMEOUT)
                    # Wait for either the messenger UI or the login form
                    page.wait_for_selector(
                        f"{_MESSENGER_LOADED}, {_LOGIN_SELECTORS}",
                        timeout=_PAGE_LOAD_TIMEOUT,
                    )
                except PlaywrightTimeout as exc:
                    raise NetworkError(
                        f"Facebook Messenger page timed out: {exc}",
                        user_message="Facebook Messenger took too long to load.",
                        action_hint="Check your internet connection.",
                    ) from exc

                # Detect login page
                current_url = page.url.lower()
                login_present = page.query_selector(_LOGIN_SELECTORS)
                if "login" in current_url or login_present:
                    raise SessionInvalidError(
                        "Facebook session expired or not initialised.",
                        user_message="Facebook is not logged in.",
                        action_hint=(
                            "Run scripts/setup_facebook_session.py to log in, "
                            "then restart the watcher."
                        ),
                    )

                # ── Find unread conversations ─────────────────────────────────
                # Strategy 1: conversations with aria-label containing "unread"
                messages.extend(self._collect_via_aria(page))

                # Strategy 2: fallback — scan visible conversation items for bold sender names
                if not messages:
                    messages.extend(self._collect_via_dom(page))

                browser.close()

        except (SessionInvalidError, AuthExpiredError, NetworkError):
            raise
        except Exception as exc:
            raise NetworkError(
                f"Facebook Messenger automation error: {exc}",
                user_message="An unexpected error occurred while checking Facebook.",
                action_hint=(
                    "Check watcher logs. If the session is corrupted, delete "
                    "FACEBOOK_SESSION_PATH and run setup_facebook_session.py again."
                ),
            ) from exc

        return messages

    def _collect_via_aria(self, page) -> list:
        """
        Primary strategy: find conversation elements whose aria-label contains
        'unread', then filter by keyword.
        """
        results = []
        try:
            # All conversation list items
            items = page.query_selector_all(
                '[role="listitem"], [role="row"], [aria-label*="conversation"]'
            )
            for item in items:
                try:
                    label = item.get_attribute("aria-label") or ""
                    if _UNREAD_CONV_PATTERN not in label.lower():
                        continue

                    # Extract sender name and preview from inner text
                    text = item.inner_text().strip()
                    lines = [l.strip() for l in text.splitlines() if l.strip()]
                    sender = lines[0] if lines else "Unknown"
                    preview = " ".join(lines[1:]) if len(lines) > 1 else ""

                    if not any(kw in (preview + sender).lower() for kw in self.keywords):
                        continue

                    results.append({
                        "sender": sender,
                        "preview": preview[:300],
                        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                        "source": "aria",
                    })
                    logger.debug("FB keyword match (aria): %s", sender)
                except Exception as exc:
                    logger.debug("FB aria item error: %s", exc)
        except Exception as exc:
            logger.debug("FB _collect_via_aria failed: %s", exc)
        return results

    def _collect_via_dom(self, page) -> list:
        """
        Fallback strategy: evaluate JS to find conversations that appear visually
        unread (bold font-weight on the sender name element).
        """
        results = []
        try:
            unread_texts = page.evaluate("""
                () => {
                    const rows = Array.from(
                        document.querySelectorAll('[role="listitem"], [role="row"]')
                    );
                    const found = [];
                    for (const row of rows) {
                        const spans = Array.from(row.querySelectorAll('span'));
                        const bold = spans.find(s => {
                            const w = window.getComputedStyle(s).fontWeight;
                            return parseInt(w) >= 700;
                        });
                        if (bold) {
                            found.push(row.innerText.trim().slice(0, 400));
                        }
                    }
                    return found;
                }
            """)
            for text in (unread_texts or []):
                lines = [l.strip() for l in text.splitlines() if l.strip()]
                sender = lines[0] if lines else "Unknown"
                preview = " ".join(lines[1:]) if len(lines) > 1 else ""
                if not any(kw in (preview + sender).lower() for kw in self.keywords):
                    continue
                results.append({
                    "sender": sender,
                    "preview": preview[:300],
                    "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                    "source": "dom_bold",
                })
                logger.debug("FB keyword match (dom): %s", sender)
        except Exception as exc:
            logger.debug("FB _collect_via_dom failed: %s", exc)
        return results

    def get_event_id(self, item: dict) -> str:
        minute_ts = item.get("timestamp", "")[:16]
        key = f"{item.get('sender', '')}::{item.get('preview', '')[:80]}::{minute_ts}"
        return hashlib.sha1(key.encode()).hexdigest()

    def create_action_file(self, item: dict) -> Path:
        """Write a structured Facebook Messenger action card to Needs_Action/."""
        sender = item.get("sender", "Unknown")
        preview = item.get("preview", "")
        received = item.get("timestamp", time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()))
        matched_kws = [kw for kw in self.keywords if kw in (preview + sender).lower()]

        content = "\n".join([
            "---",
            "type: facebook_message",
            f"sender: \"{sender}\"",
            f"received: {received}",
            f"keywords_matched: {matched_kws}",
            "priority: high",
            "status: pending",
            "---",
            "",
            f"## Facebook Messenger: {sender}",
            "",
            f"**Received**: {received}",
            f"**Keywords triggered**: {', '.join(matched_kws)}",
            "",
            "## Message Preview",
            "",
            preview,
            "",
            "## Suggested Actions",
            "- [ ] Open Facebook Messenger and reply",
            "- [ ] Check if action (invoice / payment / meeting) is required",
            "- [ ] Move to Done/ when handled",
        ])

        self.needs_action.mkdir(parents=True, exist_ok=True)
        safe_name = "".join(c if c.isalnum() or c in "-_" else "_" for c in sender)[:40]
        card_path = self.needs_action / f"FACEBOOK_{safe_name}_{int(time.time())}.md"
        card_path.write_text(content, encoding="utf-8")
        logger.info("Facebook action card written: %s", card_path.name)
        return card_path


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [FacebookWatcher] %(levelname)s: %(message)s",
    )
    FacebookWatcher().run()
