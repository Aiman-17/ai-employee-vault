"""
tests/test_silver_acceptance.py — Silver tier acceptance tests (SC-004, SC-005).

These tests validate live integration flows and require real credentials.
They are intentionally NOT run in DRY_RUN mode — set DRY_RUN=false in .env
or pass --no-dry-run flag before running.

SC-004: Gmail watcher — send test email → EMAIL_*.md appears in Needs_Action/
SC-005: WhatsApp watcher — keyword message → WHATSAPP_*.md appears in Needs_Action/

Usage:
    # Prerequisites: credentials configured, watchers running via PM2
    uv run pytest tests/test_silver_acceptance.py -v --timeout=300

    # Or run a single test:
    uv run pytest tests/test_silver_acceptance.py::SC004GmailTest -v --timeout=300
"""

import os
import time
from pathlib import Path

import pytest
from dotenv import load_dotenv

load_dotenv()

VAULT_PATH = Path(os.getenv("VAULT_PATH", "."))
NEEDS_ACTION = VAULT_PATH / "Needs_Action"
GMAIL_TOKEN_PATH = os.getenv("GMAIL_TOKEN_PATH", "")
WHATSAPP_SESSION_PATH = os.getenv("WHATSAPP_SESSION_PATH", "")

# ── SC-004: Gmail watcher ──────────────────────────────────────────────────────

@pytest.mark.skipif(
    not GMAIL_TOKEN_PATH,
    reason="GMAIL_TOKEN_PATH not set — configure Gmail credentials and run setup_gmail_auth.py first",
)
class SC004GmailTest:
    """
    SC-004: A test email sent to the monitored Gmail account appears as
    EMAIL_*.md in VAULT_PATH/Needs_Action/ within 3 minutes.

    Manual step required: send an email marked 'important' to the monitored
    Gmail account before running this test, or use the helper below.
    """

    TIMEOUT_SECONDS = 180  # 3 minutes
    POLL_INTERVAL = 10

    def test_email_action_card_created(self, tmp_path):
        """
        PASS: An EMAIL_*.md card appears in Needs_Action/ within 3 minutes
              of a new unread important email arriving in Gmail.

        This test polls Needs_Action/ for a new EMAIL_*.md file.
        Start the GmailWatcher (via PM2 or directly) before running.
        Then send a test email to the monitored account and mark it Important.
        """
        # Snapshot existing EMAIL files before the test
        existing = set(NEEDS_ACTION.glob("EMAIL_*.md"))

        deadline = time.monotonic() + self.TIMEOUT_SECONDS
        new_card: Path | None = None

        print(
            "\n[SC-004] Waiting up to 3 minutes for EMAIL_*.md to appear in Needs_Action/…"
        )
        print("  → Send a test email to the monitored account NOW (mark it Important).")

        while time.monotonic() < deadline:
            current = set(NEEDS_ACTION.glob("EMAIL_*.md"))
            new_cards = current - existing
            if new_cards:
                new_card = next(iter(new_cards))
                break
            time.sleep(self.POLL_INTERVAL)

        assert new_card is not None, (
            f"[SC-004 FAIL] No EMAIL_*.md appeared in {NEEDS_ACTION} within "
            f"{self.TIMEOUT_SECONDS}s. "
            "Check that GmailWatcher is running and the test email was marked Important."
        )

        # Validate YAML front-matter fields
        text = new_card.read_text(encoding="utf-8")
        assert "type: email" in text, f"[SC-004 FAIL] Missing 'type: email' in {new_card.name}"
        assert "from:" in text, f"[SC-004 FAIL] Missing 'from:' field in {new_card.name}"
        assert "subject:" in text, f"[SC-004 FAIL] Missing 'subject:' field in {new_card.name}"
        assert "status: pending" in text, f"[SC-004 FAIL] Missing 'status: pending' in {new_card.name}"
        assert "priority: high" in text, f"[SC-004 FAIL] Missing 'priority: high' in {new_card.name}"

        print(f"\n[SC-004 PASS] Email action card created: {new_card.name}")
        print(f"  Validated fields: type, from, subject, status, priority")


# ── SC-005: WhatsApp watcher ───────────────────────────────────────────────────

@pytest.mark.skipif(
    not WHATSAPP_SESSION_PATH,
    reason="WHATSAPP_SESSION_PATH not set — configure WhatsApp Web session first",
)
class SC005WhatsAppTest:
    """
    SC-005: A WhatsApp message containing a priority keyword appears as
    WHATSAPP_*.md in VAULT_PATH/Needs_Action/ within 90 seconds.

    Manual step required: send a WhatsApp message containing the word
    "invoice" (or another keyword from WHATSAPP_KEYWORDS) to any chat
    monitored by the agent before running this test.
    """

    TIMEOUT_SECONDS = 90
    POLL_INTERVAL = 5

    def test_whatsapp_action_card_created(self):
        """
        PASS: A WHATSAPP_*.md card appears in Needs_Action/ within 90 seconds
              of a keyword message arriving in WhatsApp Web.

        Start the WhatsAppWatcher (via PM2 or directly) before running.
        Then send a WhatsApp message containing "invoice" to any monitored chat.
        """
        existing = set(NEEDS_ACTION.glob("WHATSAPP_*.md"))

        deadline = time.monotonic() + self.TIMEOUT_SECONDS
        new_card: Path | None = None

        print(
            "\n[SC-005] Waiting up to 90 seconds for WHATSAPP_*.md to appear in Needs_Action/…"
        )
        print('  → Send a WhatsApp message containing "invoice" to any chat NOW.')

        while time.monotonic() < deadline:
            current = set(NEEDS_ACTION.glob("WHATSAPP_*.md"))
            new_cards = current - existing
            if new_cards:
                new_card = next(iter(new_cards))
                break
            time.sleep(self.POLL_INTERVAL)

        assert new_card is not None, (
            f"[SC-005 FAIL] No WHATSAPP_*.md appeared in {NEEDS_ACTION} within "
            f"{self.TIMEOUT_SECONDS}s. "
            "Check that WhatsAppWatcher is running and WhatsApp Web session is authenticated."
        )

        # Validate YAML front-matter fields
        text = new_card.read_text(encoding="utf-8")
        assert "type: whatsapp" in text, f"[SC-005 FAIL] Missing 'type: whatsapp' in {new_card.name}"
        assert "chat:" in text, f"[SC-005 FAIL] Missing 'chat:' field in {new_card.name}"
        assert "keywords_matched:" in text, f"[SC-005 FAIL] Missing 'keywords_matched:' in {new_card.name}"
        assert "status: pending" in text, f"[SC-005 FAIL] Missing 'status: pending' in {new_card.name}"

        print(f"\n[SC-005 PASS] WhatsApp action card created: {new_card.name}")
        print(f"  Validated fields: type, chat, keywords_matched, status")


# ── SC-006: Finance watcher (bonus — no credentials needed, just a CSV) ───────

class SC006FinanceTest:
    """
    SC-006: Dropping a CSV file into BANK_CSV_DROP_PATH updates
    Accounting/Current_Month.md within 5 minutes.

    Requires BANK_CSV_DROP_PATH to be set in .env.
    """

    TIMEOUT_SECONDS = 300  # 5 minutes
    POLL_INTERVAL = 15

    @pytest.mark.skipif(
        not os.getenv("BANK_CSV_DROP_PATH"),
        reason="BANK_CSV_DROP_PATH not set",
    )
    def test_finance_csv_processed(self, tmp_path):
        """
        PASS: Dropping a CSV into BANK_CSV_DROP_PATH causes
              Accounting/Current_Month.md to gain new rows within 5 minutes.
        """
        import csv
        import datetime

        drop_path = Path(os.getenv("BANK_CSV_DROP_PATH", ""))
        accounting_file = VAULT_PATH / "Accounting" / "Current_Month.md"

        # Record current line count
        initial_lines = (
            accounting_file.read_text(encoding="utf-8").splitlines()
            if accounting_file.exists()
            else []
        )

        # Write a minimal test CSV
        ts = int(time.time())
        test_csv = drop_path / f"test_bank_{ts}.csv"
        with test_csv.open("w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=["date", "description", "amount", "balance"])
            writer.writeheader()
            writer.writerow({
                "date": datetime.date.today().isoformat(),
                "description": "SC006 Test Transaction",
                "amount": "-9.99",
                "balance": "1000.00",
            })

        print(f"\n[SC-006] Dropped test CSV: {test_csv.name}")
        print(f"  Waiting up to 5 minutes for Accounting/Current_Month.md to update…")

        deadline = time.monotonic() + self.TIMEOUT_SECONDS
        updated = False

        while time.monotonic() < deadline:
            if accounting_file.exists():
                current_lines = accounting_file.read_text(encoding="utf-8").splitlines()
                if len(current_lines) > len(initial_lines):
                    updated = True
                    break
            time.sleep(self.POLL_INTERVAL)

        # Clean up test CSV regardless of outcome
        if test_csv.exists():
            test_csv.unlink()

        assert updated, (
            f"[SC-006 FAIL] Accounting/Current_Month.md was not updated within "
            f"{self.TIMEOUT_SECONDS}s after dropping {test_csv.name}. "
            "Check that FinanceWatcher is running."
        )

        print("\n[SC-006 PASS] Accounting/Current_Month.md updated after CSV drop.")
