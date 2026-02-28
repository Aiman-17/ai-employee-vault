"""
src/watchers/finance_watcher.py — Finance / bank CSV drop-folder watcher (Silver tier).

Watches BANK_CSV_DROP_PATH for new CSV files from bank exports (Wise, Revolut,
local bank CSV statements). For each new file it:

  1. Parses the CSV into transactions (pandas preferred, csv.DictReader fallback).
  2. Appends a Markdown summary to VAULT_PATH/Accounting/Current_Month.md.
  3. Flags suspicious/subscription transactions using audit_logic patterns.
  4. Writes a structured action card to VAULT_PATH/Needs_Action/ for Claude.

Environment variables:
    BANK_CSV_DROP_PATH   Directory where bank CSV exports are saved (required).
    VAULT_PATH           Obsidian vault root.

Column name mapping (auto-detects common bank export formats):
    Date     : Date, date, DATE, Transaction Date, Completed Date, ValueDate
    Amount   : Amount, amount, Credit/Debit, Debit, Credit, Withdrawal Amount
    Description: Description, Payee, Merchant, Narrative, Reference, Details

Error philosophy:
    - Unreadable/malformed CSV → ParseError → quarantine card written
    - Missing columns          → ParseError with user-friendly hint
    - Permission denied        → VaultLockError
"""

import csv
import hashlib
import logging
import os
import queue
import time
from io import StringIO
from pathlib import Path

from dotenv import load_dotenv
from watchdog.events import FileSystemEventHandler
from watchdog.observers import Observer

from src.audit import audit_logic
from src.exceptions import ParseError, VaultLockError
from src.watchers.base_watcher import BaseWatcher

load_dotenv()

logger = logging.getLogger(__name__)

# Common column name aliases for bank CSV exports
_DATE_COLS = ["date", "transaction date", "completed date", "valuedate", "booking date"]
_AMOUNT_COLS = ["amount", "credit/debit", "debit", "credit", "withdrawal amount", "transaction amount"]
_DESC_COLS = ["description", "payee", "merchant", "narrative", "reference", "details", "memo"]


class _CSVDropHandler(FileSystemEventHandler):
    """Feeds newly created CSV files into the watcher's queue."""

    def __init__(self, event_queue: queue.Queue):
        super().__init__()
        self._queue = event_queue

    def on_created(self, event):
        if event.is_directory:
            return
        src = Path(event.src_path)
        if src.suffix.lower() == ".csv":
            logger.debug("Finance drop: new CSV detected — %s", src.name)
            self._queue.put(src)


class FinanceWatcher(BaseWatcher):
    """
    Silver-tier watcher: monitors a bank CSV drop folder for new statements.

    Environment variables:
        BANK_CSV_DROP_PATH  Directory to watch for .csv bank exports.
        VAULT_PATH          Obsidian vault root.
    """

    def __init__(self, check_interval: int = 3600):
        super().__init__(check_interval=check_interval)

        drop = os.getenv("BANK_CSV_DROP_PATH") or os.getenv("FILE_DROP_PATH")
        if not drop:
            logger.warning(
                "BANK_CSV_DROP_PATH is not set. FinanceWatcher will not monitor anything. "
                "Add BANK_CSV_DROP_PATH=/path/to/bank_exports to .env and restart."
            )
        self.drop_path: Path | None = Path(drop) if drop else None

        # Separate queue for CSV files detected by watchdog
        self._queue: queue.Queue = queue.Queue()
        self._observer: Observer | None = None

    # ── BaseWatcher interface ─────────────────────────────────────────────────

    def check_for_updates(self) -> list:
        """Drain the queue and return all waiting CSV file paths."""
        items = []
        while True:
            try:
                items.append(self._queue.get_nowait())
            except queue.Empty:
                break
        return items

    def get_event_id(self, item: Path) -> str:
        """Stable ID: SHA-1 of resolved file path (idempotent across reboots)."""
        return hashlib.sha1(str(item.resolve()).encode()).hexdigest()

    def create_action_file(self, item: Path) -> Path:
        """
        Parse the CSV, append to Accounting/Current_Month.md, flag subscriptions,
        and write an action card to Needs_Action/.
        """
        if not item.exists():
            raise ParseError(
                f"CSV file disappeared before processing: {item}",
                user_message=f"The file '{item.name}' was removed before processing.",
                action_hint="Drop the file again — make sure nothing else is moving it.",
            )

        try:
            transactions = self._parse_csv(item)
        except ParseError:
            raise
        except Exception as exc:
            raise ParseError(
                f"Failed to parse {item.name}: {exc}",
                user_message=f"The file '{item.name}' could not be read as a bank CSV.",
                action_hint=(
                    "Make sure the file is a valid UTF-8 or Latin-1 CSV. "
                    "Export from your bank app using the 'CSV' option."
                ),
            ) from exc

        if not transactions:
            logger.info("CSV %s contained no transactions — skipping.", item.name)
            return self.needs_action / f"FINANCE_empty_{item.stem}.md"

        # Append transactions to Accounting/Current_Month.md
        accounting_path = self.vault_path / "Accounting" / "Current_Month.md"
        self._append_to_accounting(transactions, accounting_path, item.name)

        # Detect subscription / flagged transactions
        flagged = [
            t for t in transactions
            if audit_logic.analyze_transaction(t) is not None
        ]

        # Write action card to Needs_Action/
        card_path = self._write_finance_card(transactions, flagged, item)
        logger.info(
            "Finance card written: %s (%d transactions, %d flagged)",
            card_path.name,
            len(transactions),
            len(flagged),
        )
        return card_path

    # ── CSV parsing ───────────────────────────────────────────────────────────

    def _parse_csv(self, csv_path: Path) -> list[dict]:
        """
        Parse a bank CSV file into a list of standardised transaction dicts.
        Tries pandas first, falls back to csv.DictReader.
        Returns list of dicts with keys: date, amount, description.
        """
        # Try pandas for robust encoding and format handling
        try:
            import pandas as pd
            df = pd.read_csv(
                csv_path,
                encoding="utf-8-sig",  # handles BOM from Excel exports
                on_bad_lines="skip",
            )
            # Normalise column names
            df.columns = [c.strip().lower() for c in df.columns]
            return self._normalise_dataframe(df, csv_path.name)
        except ImportError:
            pass  # pandas not installed; fall back to csv module
        except Exception as exc:
            logger.debug("pandas parse failed for %s: %s — trying csv module", csv_path.name, exc)

        # Fallback: csv.DictReader
        try:
            raw = csv_path.read_bytes()
            for encoding in ("utf-8-sig", "utf-8", "latin-1"):
                try:
                    text = raw.decode(encoding)
                    break
                except UnicodeDecodeError:
                    continue
            else:
                raise ParseError(
                    f"Cannot decode {csv_path.name} — unknown encoding.",
                    user_message=f"The file '{csv_path.name}' uses an unsupported encoding.",
                    action_hint="Try re-exporting from your bank as UTF-8 CSV.",
                )

            reader = csv.DictReader(StringIO(text))
            rows = list(reader)
            if not rows:
                return []
            normalised = [self._normalise_row(r) for r in rows]
            return [r for r in normalised if r is not None]
        except ParseError:
            raise
        except Exception as exc:
            raise ParseError(
                f"csv module parse failed for {csv_path.name}: {exc}",
            ) from exc

    def _normalise_dataframe(self, df, filename: str) -> list[dict]:
        """Extract date/amount/description columns from a pandas DataFrame."""
        col_map = {}
        for col in df.columns:
            if col in _DATE_COLS and "date" not in col_map:
                col_map["date"] = col
            if col in _AMOUNT_COLS and "amount" not in col_map:
                col_map["amount"] = col
            if col in _DESC_COLS and "description" not in col_map:
                col_map["description"] = col

        if "amount" not in col_map:
            raise ParseError(
                f"No amount column found in {filename}. Available: {list(df.columns)}",
                user_message=f"Could not find a transaction amount column in '{filename}'.",
                action_hint=(
                    "Expected one of: Amount, Credit/Debit, Debit, Credit. "
                    "Check your bank export settings."
                ),
            )

        results = []
        for _, row in df.iterrows():
            results.append({
                "date": str(row.get(col_map.get("date", ""), "")).strip(),
                "amount": str(row.get(col_map.get("amount", ""), "0")).strip(),
                "description": str(row.get(col_map.get("description", ""), "")).strip(),
            })
        return results

    def _normalise_row(self, row: dict) -> dict | None:
        """Normalise a csv.DictReader row to standard keys."""
        row_lower = {k.strip().lower(): v for k, v in row.items()}
        amount_val = next(
            (row_lower[c] for c in _AMOUNT_COLS if c in row_lower),
            None,
        )
        if amount_val is None:
            return None
        return {
            "date": next((row_lower[c] for c in _DATE_COLS if c in row_lower), ""),
            "amount": amount_val.strip(),
            "description": next((row_lower[c] for c in _DESC_COLS if c in row_lower), ""),
        }

    # ── Accounting log ────────────────────────────────────────────────────────

    def _append_to_accounting(
        self, transactions: list[dict], accounting_path: Path, source_file: str
    ) -> None:
        """Append a Markdown transaction block to Accounting/Current_Month.md."""
        try:
            accounting_path.parent.mkdir(parents=True, exist_ok=True)
            lines = [
                "",
                f"## Import: {source_file} — {time.strftime('%Y-%m-%d %H:%M UTC', time.gmtime())}",
                "",
                "| Date | Amount | Description |",
                "|------|--------|-------------|",
            ]
            for t in transactions:
                lines.append(f"| {t['date']} | {t['amount']} | {t['description']} |")
            lines.append("")

            with accounting_path.open("a", encoding="utf-8") as fh:
                fh.write("\n".join(lines))
            logger.info("Appended %d rows to %s", len(transactions), accounting_path)
        except PermissionError as exc:
            raise VaultLockError(
                str(exc),
                user_message="Cannot write to the Accounting folder — permission denied.",
                action_hint="Check that VAULT_PATH/Accounting/ is writable.",
            ) from exc

    # ── Action card ───────────────────────────────────────────────────────────

    def _write_finance_card(
        self, transactions: list[dict], flagged: list[dict], source: Path
    ) -> Path:
        """Write a Needs_Action/ card summarising the CSV import."""
        received = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        total = len(transactions)
        flag_count = len(flagged)

        lines = [
            "---",
            "type: finance_import",
            f"source_file: {source.name}",
            f"transaction_count: {total}",
            f"flagged_count: {flag_count}",
            f"received: {received}",
            "priority: high" if flag_count > 0 else "priority: medium",
            "status: pending",
            "---",
            "",
            f"## Finance Import: {source.name}",
            "",
            f"- **Transactions**: {total}",
            f"- **Flagged (subscriptions / unusual)**: {flag_count}",
            f"- **Imported**: {received}",
            "",
        ]

        if flagged:
            lines += [
                "## Flagged Transactions",
                "",
                "| Date | Amount | Description | Flag |",
                "|------|--------|-------------|------|",
            ]
            for t in flagged:
                analysis = audit_logic.analyze_transaction(t) or {}
                flag_name = analysis.get("name", "Unknown")
                lines.append(f"| {t['date']} | {t['amount']} | {t['description']} | {flag_name} |")
            lines += [
                "",
                "## Suggested Actions",
                "- [ ] Review flagged subscriptions in Obsidian",
                "- [ ] Cancel unused subscriptions (move approval to Pending_Approval/)",
                "- [ ] Reconcile with Business_Goals.md budget",
            ]

        self.needs_action.mkdir(parents=True, exist_ok=True)
        card_path = self.needs_action / f"FINANCE_{source.stem}_{int(time.time())}.md"
        card_path.write_text("\n".join(lines), encoding="utf-8")
        return card_path

    # ── Lifecycle ─────────────────────────────────────────────────────────────

    def run(self) -> None:
        """Start the watchdog Observer for CSVs, then enter the BaseWatcher run loop."""
        if not self.drop_path:
            logger.error(
                "FinanceWatcher cannot start — BANK_CSV_DROP_PATH is not set. "
                "Set it in .env and restart."
            )
            return

        if not self.drop_path.exists():
            logger.info("CSV drop folder does not exist — creating: %s", self.drop_path)
            self.drop_path.mkdir(parents=True, exist_ok=True)

        handler = _CSVDropHandler(self._queue)
        self._observer = Observer()
        self._observer.schedule(handler, str(self.drop_path), recursive=False)
        self._observer.start()
        logger.info("Watching bank CSV drop folder: %s", self.drop_path)

        try:
            super().run()
        finally:
            self._observer.stop()
            self._observer.join()
            logger.info("FinanceWatcher stopped.")


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [FinanceWatcher] %(levelname)s: %(message)s",
    )
    FinanceWatcher().run()
