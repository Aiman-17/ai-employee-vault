"""
src/watchers/instagram_watcher.py — Instagram DM perception layer.

Uses Playwright (headless Chromium) with a persistent session to monitor
Instagram Direct Messages for keyword-matching conversations.
No access tokens required — just a saved browser login session.

⚠️  Meta Terms of Service: Automation of instagram.com is technically against
    Meta's ToS.  Use only for personal productivity on your own account and
    comply with applicable laws.  Do not use for bulk operations.

Prerequisites:
    pip install playwright
    playwright install chromium

Environment variables:
    INSTAGRAM_SESSION_PATH  Directory where Playwright saves the browser session.
    INSTAGRAM_KEYWORDS      Comma-separated keywords to filter DMs (default below).
    VAULT_PATH              Obsidian vault root.

Authentication flow:
    1. First run: run scripts/setup_instagram_session.py — log in manually.
    2. Subsequent runs: session reloaded headlessly from INSTAGRAM_SESSION_PATH.
    3. If session expires: SessionInvalidError → error card in Needs_Action/.

Detection strategy (confirmed via DOM inspection 2026-02-28):
    - Loaded indicator: [aria-label="Thread list"]
    - Unread count: page title prefix "(N) Instagram • Messages"
    - Unread senders: bold font-weight (>= 700) leaf nodes in the thread list
    - Preview: sibling text in the same container (line after sender name)
    - Instagram uses obfuscated class names — avoid class selectors entirely.
"""

import hashlib
import logging
import os
import re
import time
from pathlib import Path

from dotenv import load_dotenv

from src.exceptions import AuthExpiredError, NetworkError, SessionInvalidError
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
    "collab",
    "collaboration",
    "price",
    "order",
]

_DM_INBOX_URL = "https://www.instagram.com/direct/inbox/"
_PAGE_LOAD_TIMEOUT = 60_000  # ms

# Login form present → not logged in
_LOGIN_SEL = (
    '[aria-label="Phone number, username, or email"], '
    'input[name="username"], '
    'form#loginForm'
)

# DM inbox loaded — confirmed working selector
_THREAD_LIST_SEL = '[aria-label="Thread list"]'

# UI strings that appear bold but are not DM sender names — filter these out
_UI_STRINGS = {
    "messages", "requests", "search", "new message", "direct messaging",
    "inbox", "notifications", "home", "reels", "explore",
}

# JS to find unread thread senders + previews via bold font-weight detection
_FIND_BOLD_JS = """
() => {
    const results = [];
    const seen = new Set();
    const allEls = document.querySelectorAll("*");
    for (const el of allEls) {
        if (el.children.length > 0) continue;
        const txt = (el.innerText || "").trim();
        if (!txt || txt.length < 2 || txt.length > 60 || seen.has(txt)) continue;
        const fw = parseInt(window.getComputedStyle(el).fontWeight);
        if (fw < 700) continue;
        const r = el.getBoundingClientRect();
        if (r.width === 0 || r.height === 0) continue;
        seen.add(txt);

        // Walk up 2-3 levels to get a container with sender + preview (2-4 lines)
        let container = el.parentElement;
        for (let i = 0; i < 5; i++) {
            if (!container) break;
            const lines = (container.innerText || "").trim().split("\\n")
                          .map(x => x.trim()).filter(x => x.length > 0);
            if (lines.length >= 2 && lines.length <= 5) break;
            container = container.parentElement;
        }
        const lines = container
            ? (container.innerText || "").trim().split("\\n")
              .map(x => x.trim()).filter(x => x.length > 0)
            : [txt];
        results.push({ sender: txt, lines: lines.slice(0, 3) });
    }
    return results;
}
"""


class InstagramWatcher(BaseWatcher):
    """
    Browser-based watcher: monitors Instagram DMs for keyword messages.

    No API token required — uses a saved Playwright browser session.

    Environment variables:
        INSTAGRAM_SESSION_PATH  Path to Playwright persistent context directory.
        INSTAGRAM_KEYWORDS      Comma-separated list of trigger keywords.
        VAULT_PATH              Obsidian vault root.
    """

    def __init__(self, check_interval: int = 60):
        super().__init__(check_interval=check_interval)

        session_dir = os.getenv("INSTAGRAM_SESSION_PATH", "credentials/instagram_session")
        self.session_path = Path(session_dir)

        raw_keywords = os.getenv("INSTAGRAM_KEYWORDS", "")
        self.keywords = (
            [k.strip().lower() for k in raw_keywords.split(",") if k.strip()]
            if raw_keywords
            else _DEFAULT_KEYWORDS
        )

        logger.info(
            "InstagramWatcher configured — keywords: %s, session: %s",
            self.keywords,
            self.session_path,
        )

    # ── BaseWatcher interface ─────────────────────────────────────────────────

    def check_for_updates(self) -> list:
        """
        Open Instagram DM inbox, find unread conversations with keyword matches.
        Returns a list of dicts with keys: sender, preview, timestamp.
        """
        try:
            from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeout
        except ImportError as exc:
            raise AuthExpiredError(
                f"Playwright not installed: {exc}",
                user_message="Instagram monitoring requires Playwright.",
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
                    page.goto(_DM_INBOX_URL, timeout=_PAGE_LOAD_TIMEOUT)
                    # Wait for the thread list OR login form
                    page.wait_for_selector(
                        f"{_THREAD_LIST_SEL}, {_LOGIN_SEL}",
                        timeout=_PAGE_LOAD_TIMEOUT,
                    )
                except PlaywrightTimeout as exc:
                    raise NetworkError(
                        f"Instagram DM inbox timed out: {exc}",
                        user_message="Instagram DM inbox took too long to load.",
                        action_hint="Check your internet connection.",
                    ) from exc

                # Detect login redirect
                current_url = page.url.lower()
                login_present = page.query_selector(_LOGIN_SEL)
                if "login" in current_url or "/accounts/login" in current_url or login_present:
                    raise SessionInvalidError(
                        "Instagram session expired or not initialised.",
                        user_message="Instagram is not logged in.",
                        action_hint=(
                            "Run scripts/setup_instagram_session.py to log in, "
                            "then restart the watcher."
                        ),
                    )

                # Quick check: does the title say there are unread messages?
                title = page.title()
                m = re.match(r"\((\d+)\)", title)
                unread_total = int(m.group(1)) if m else 0
                logger.debug("Instagram title unread count: %d", unread_total)

                if unread_total == 0:
                    logger.debug("No unread Instagram DMs — skipping DOM scan.")
                    browser.close()
                    return []

                # Let virtualized list fully render before scanning
                page.wait_for_timeout(4000)

                # Dismiss popups if present
                self._dismiss_popups(page)

                # Find unread senders via bold font-weight detection
                raw_items = page.evaluate(_FIND_BOLD_JS)
                messages = self._filter_items(raw_items)

                browser.close()

        except (SessionInvalidError, AuthExpiredError, NetworkError):
            raise
        except Exception as exc:
            raise NetworkError(
                f"Instagram DM automation error: {exc}",
                user_message="An unexpected error occurred while checking Instagram.",
                action_hint=(
                    "Check watcher logs. If the session is corrupted, delete "
                    "INSTAGRAM_SESSION_PATH and run setup_instagram_session.py again."
                ),
            ) from exc

        return messages

    def _dismiss_popups(self, page) -> None:
        """Silently dismiss common Instagram popups."""
        for label in ["Not Now", "Dismiss", "Close", "Allow all cookies", "Decline optional cookies"]:
            try:
                btn = page.query_selector(f'[aria-label="{label}"], button:has-text("{label}")')
                if btn:
                    btn.click()
                    page.wait_for_timeout(400)
            except Exception:
                pass

    def _filter_items(self, raw_items: list) -> list:
        """
        Filter bold items to real DM senders with keyword matches.
        Removes UI strings (Messages, Requests, etc.) and non-matching items.
        """
        results = []
        seen_senders = set()
        for item in raw_items:
            sender = item.get("sender", "").strip()
            if not sender or sender.lower() in _UI_STRINGS:
                continue
            if sender in seen_senders:
                continue
            seen_senders.add(sender)

            lines = item.get("lines", [sender])
            # line[0] is the sender; line[1] onward is the preview
            preview = " ".join(lines[1:2]) if len(lines) > 1 else ""

            combined = (sender + " " + preview).lower()
            if not any(kw in combined for kw in self.keywords):
                continue

            results.append({
                "sender": sender,
                "preview": preview[:300],
                "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            })
            logger.debug("Instagram keyword match: %s", sender)

        return results

    def get_event_id(self, item: dict) -> str:
        minute_ts = item.get("timestamp", "")[:16]
        key = f"{item.get('sender', '')}::{item.get('preview', '')[:80]}::{minute_ts}"
        return hashlib.sha1(key.encode()).hexdigest()

    def create_action_file(self, item: dict) -> Path:
        """Write a structured Instagram DM action card to Needs_Action/."""
        sender = item.get("sender", "Unknown")
        preview = item.get("preview", "")
        received = item.get("timestamp", time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()))
        matched_kws = [kw for kw in self.keywords if kw in (preview + sender).lower()]

        content = "\n".join([
            "---",
            "type: instagram_dm",
            f"sender: \"{sender}\"",
            f"received: {received}",
            f"keywords_matched: {matched_kws}",
            "priority: high",
            "status: pending",
            "---",
            "",
            f"## Instagram DM: {sender}",
            "",
            f"**Received**: {received}",
            f"**Keywords triggered**: {', '.join(matched_kws)}",
            "",
            "## Message Preview",
            "",
            preview,
            "",
            "## Suggested Actions",
            "- [ ] Open Instagram and reply to the DM",
            "- [ ] Check if action (collab / invoice / meeting) is required",
            "- [ ] Move to Done/ when handled",
        ])

        self.needs_action.mkdir(parents=True, exist_ok=True)
        safe_name = "".join(c if c.isalnum() or c in "-_" else "_" for c in sender)[:40]
        card_path = self.needs_action / f"INSTAGRAM_{safe_name}_{int(time.time())}.md"
        card_path.write_text(content, encoding="utf-8")
        logger.info("Instagram action card written: %s", card_path.name)
        return card_path


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [InstagramWatcher] %(levelname)s: %(message)s",
    )
    InstagramWatcher().run()
