"""
src/watchers/whatsapp_watcher.py — WhatsApp Web perception layer (Silver tier).

Uses Playwright (headless Chromium) to monitor WhatsApp Web for unread messages
containing business-relevant keywords. Writes structured action cards to
VAULT_PATH/Needs_Action/ for Claude to reason about.

⚠️  WhatsApp Terms of Service: Automation of WhatsApp Web is technically against
    Meta's ToS. Use only for personal productivity and comply with applicable laws.
    Do not use for bulk messaging or commercial scale.

Prerequisites:
    pip install playwright
    playwright install chromium

Environment variables:
    WHATSAPP_SESSION_PATH   Directory where Playwright saves the browser session.
                            Persist this between runs to avoid re-scanning QR.
    WHATSAPP_KEYWORDS       Comma-separated keywords to filter messages (default below).
    VAULT_PATH              Obsidian vault root.

Authentication flow:
    1. First run: WhatsApp Web opens in a visible window. Scan the QR code.
    2. Subsequent runs: session is reloaded from WHATSAPP_SESSION_PATH (headless).
    3. If the session expires: SessionInvalidError → error card in Needs_Action/.

Error philosophy:
    - Session disconnected  → SessionInvalidError → user prompted to re-scan QR
    - Browser launch fails  → AuthExpiredError    → install playwright hint
    - Page timeout          → NetworkError        → retry on next cycle
    - Malformed message     → ParseError          → quarantine card
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

# Default business-critical keywords to watch for
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
]

_WHATSAPP_URL = "https://web.whatsapp.com"
_PAGE_LOAD_TIMEOUT = 60_000  # ms


class WhatsAppWatcher(BaseWatcher):
    """
    Silver-tier watcher: monitors WhatsApp Web for keyword-matching messages.

    Environment variables:
        WHATSAPP_SESSION_PATH   Path to Playwright persistent context directory.
        WHATSAPP_KEYWORDS       Comma-separated list of trigger keywords.
        VAULT_PATH              Obsidian vault root.
    """

    def __init__(self, check_interval: int = 30):
        super().__init__(check_interval=check_interval)

        session_dir = os.getenv("WHATSAPP_SESSION_PATH", "credentials/whatsapp_session")
        self.session_path = Path(session_dir)

        raw_keywords = os.getenv("WHATSAPP_KEYWORDS", "")
        if raw_keywords:
            self.keywords = [k.strip().lower() for k in raw_keywords.split(",") if k.strip()]
        else:
            self.keywords = _DEFAULT_KEYWORDS

        logger.info(
            "WhatsAppWatcher configured — keywords: %s, session: %s",
            self.keywords,
            self.session_path,
        )

    # ── BaseWatcher interface ─────────────────────────────────────────────────

    def check_for_updates(self) -> list:
        """
        Open WhatsApp Web, find unread chats with keyword matches, return items.
        Each item is a dict with keys: chat_name, message_preview, timestamp.
        Returns an empty list if no matching messages found.
        """
        try:
            from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeout
        except ImportError as exc:
            raise AuthExpiredError(
                f"Playwright not installed: {exc}",
                user_message="WhatsApp monitoring requires Playwright to be installed.",
                action_hint=(
                    "Run:\n"
                    "  pip install playwright\n"
                    "  playwright install chromium"
                ),
            ) from exc

        self.session_path.mkdir(parents=True, exist_ok=True)
        headless = os.getenv("AGENT_MODE", "local") != "local"  # headless for cloud

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
                    page.goto(_WHATSAPP_URL, timeout=_PAGE_LOAD_TIMEOUT)
                    # WhatsApp Web uses aria-label on the chat list (testid removed in newer builds)
                    page.wait_for_selector(
                        '[aria-label="Chat list"], [data-testid="chat-list"]',
                        timeout=_PAGE_LOAD_TIMEOUT,
                    )
                except PlaywrightTimeout as exc:
                    raise NetworkError(
                        f"WhatsApp Web page timed out: {exc}",
                        user_message="WhatsApp Web took too long to load.",
                        action_hint=(
                            "Check your internet connection. "
                            "If the QR code appeared, scan it and restart the watcher."
                        ),
                    ) from exc

                # Check for QR code / logged out state
                if page.query_selector('[data-testid="qrcode"]') or page.query_selector('canvas[aria-label*="QR"]'):
                    raise SessionInvalidError(
                        "WhatsApp Web is showing QR code — session not initialised.",
                        user_message="WhatsApp is not logged in.",
                        action_hint=(
                            "Stop the watcher, set AGENT_MODE=local (non-headless), "
                            "run it manually, and scan the QR code in the browser."
                        ),
                    )

                # Find unread chat items (aria-label selector works across WA builds)
                unread_chats = page.query_selector_all(
                    '[aria-label="Chat list"] [role="listitem"], '
                    '[data-testid="cell-frame-container"]'
                )
                for chat in unread_chats:
                    try:
                        # Check for unread badge (testid or aria-label variant)
                        badge = (
                            chat.query_selector('[data-testid="icon-unread-count"]')
                            or chat.query_selector('span[aria-label*="unread"]')
                        )
                        if not badge:
                            continue

                        # Get chat name and message preview
                        name_el = chat.query_selector('[data-testid="cell-frame-title"]')
                        preview_el = chat.query_selector('[data-testid="last-msg-cell"]')

                        chat_name = name_el.inner_text() if name_el else "Unknown"
                        preview = preview_el.inner_text() if preview_el else ""

                        preview_lower = preview.lower()
                        if any(kw in preview_lower for kw in self.keywords):
                            messages.append({
                                "chat_name": chat_name,
                                "message_preview": preview,
                                "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                            })
                            logger.debug("Keyword match in chat: %s", chat_name)
                    except Exception as exc:
                        logger.debug("Error reading chat element: %s — skipping", exc)
                        continue

                browser.close()
        except (SessionInvalidError, AuthExpiredError, NetworkError):
            raise
        except Exception as exc:
            raise NetworkError(
                f"WhatsApp Web automation error: {exc}",
                user_message="An unexpected error occurred while checking WhatsApp.",
                action_hint=(
                    "Check the watcher logs. "
                    "If the session seems corrupted, delete WHATSAPP_SESSION_PATH and re-scan."
                ),
            ) from exc

        return messages

    def get_event_id(self, item: dict) -> str:
        """
        Stable ID: hash of chat_name + message_preview + minute-level timestamp.
        Minute-level granularity prevents re-processing on restart within the same minute
        but catches new messages in subsequent checks.
        """
        minute_ts = item.get("timestamp", "")[:16]  # YYYY-MM-DDTHH:MM
        key = f"{item.get('chat_name', '')}::{item.get('message_preview', '')[:80]}::{minute_ts}"
        return hashlib.sha1(key.encode()).hexdigest()

    def create_action_file(self, item: dict) -> Path:
        """Write a structured WhatsApp action card to Needs_Action/."""
        chat_name = item.get("chat_name", "Unknown")
        preview = item.get("message_preview", "")
        received = item.get("timestamp", time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()))

        matched_kws = [kw for kw in self.keywords if kw in preview.lower()]

        content = "\n".join([
            "---",
            "type: whatsapp_message",
            f"chat: \"{chat_name}\"",
            f"received: {received}",
            f"keywords_matched: {matched_kws}",
            "priority: high",
            "status: pending",
            "---",
            "",
            f"## WhatsApp: {chat_name}",
            "",
            f"**Received**: {received}",
            f"**Keywords triggered**: {', '.join(matched_kws)}",
            "",
            "## Message Preview",
            "",
            preview,
            "",
            "## Suggested Actions",
            "- [ ] Open WhatsApp and reply",
            "- [ ] Check if action (invoice / payment / meeting) is required",
            "- [ ] Move to Done/ when handled",
        ])

        self.needs_action.mkdir(parents=True, exist_ok=True)
        safe_name = "".join(c if c.isalnum() or c in "-_" else "_" for c in chat_name)
        card_path = self.needs_action / f"WHATSAPP_{safe_name}_{int(time.time())}.md"
        card_path.write_text(content, encoding="utf-8")
        logger.info("WhatsApp action card written: %s", card_path.name)
        return card_path


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [WhatsAppWatcher] %(levelname)s: %(message)s",
    )
    WhatsAppWatcher().run()
