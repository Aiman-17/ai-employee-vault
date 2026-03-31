"""
src/watchers/base_watcher.py — Abstract base class for all Digital FTE watchers.

Every watcher (Gmail, WhatsApp, Filesystem, Finance) extends BaseWatcher and
implements three abstract methods. The run() loop handles retries, idempotency,
graceful shutdown, and error escalation automatically.

Error philosophy (user-friendly):
  - Transient errors  → auto-retry with backoff; log a friendly warning
  - Auth errors       → write an Obsidian error card to Needs_Action/; pause
  - Data errors       → quarantine the item; continue processing others
  - Constitutional    → halt immediately; write breach notice; alert human
"""

import logging
import os
import tempfile
import time
from abc import ABC, abstractmethod
from pathlib import Path

from dotenv import load_dotenv

from src import state_manager
from src.audit import audit_logger
from src.exceptions import (
    AuthExpiredError,
    ConstitutionalBreachError,
    DuplicateItemError,
    NetworkError,
    ParseError,
    RateLimitError,
    SessionInvalidError,
    WatcherError,
)
from src.retry_handler import with_retry

load_dotenv()

logger = logging.getLogger(__name__)


class BaseWatcher(ABC):
    """
    Abstract base for all Digital FTE perception layer watchers.

    Subclasses must implement:
        check_for_updates() -> list       — poll the source; return new items
        create_action_file(item) -> Path  — write item to Needs_Action/ as .md
        get_event_id(item) -> str         — stable unique ID for idempotency
    """

    def __init__(self, check_interval: int = 60):
        self.check_interval = check_interval
        self._running = False

        vault = os.getenv("VAULT_PATH", "")
        if not vault:
            logger.warning(
                "VAULT_PATH is not set. Watcher %s will use the current directory. "
                "Run scripts/setup_vault.py after setting VAULT_PATH in .env.",
                self.__class__.__name__,
            )
        self.vault_path = Path(vault) if vault else Path(".")
        self.needs_action = self.vault_path / "Needs_Action"

        # Load persisted processed-ID set for idempotency
        state = state_manager.load_state(self.__class__.__name__)
        self._processed_ids: set[str] = set(state.get("processed_ids", []))

    # ── Abstract interface ────────────────────────────────────────────────────

    @abstractmethod
    def check_for_updates(self) -> list:
        """Poll the source and return a list of new items to process."""

    @abstractmethod
    def create_action_file(self, item) -> Path:
        """Write a structured .md file to Needs_Action/ for the given item."""

    @abstractmethod
    def get_event_id(self, item) -> str:
        """Return a stable, unique string ID for *item* (used for idempotency)."""

    # ── Run loop ──────────────────────────────────────────────────────────────

    def run(self) -> None:
        """
        Main watcher loop. Runs until stop() is called or a constitutional breach.
        Handles all recoverable errors internally; only propagates fatal ones.
        """
        self._running = True
        logger.info("%s started (interval: %ds).", self.__class__.__name__, self.check_interval)

        while self._running:
            try:
                self._tick()
            except ConstitutionalBreachError as exc:
                # Safety stop — do not retry
                logger.critical(
                    "%s halted: Constitutional breach — %s",
                    self.__class__.__name__,
                    exc.user_message,
                )
                self._write_error_card("BREACH", exc)
                audit_logger.log_error(
                    actor=self.__class__.__name__,
                    error_type="ConstitutionalBreach",
                    user_message=exc.user_message,
                    action_hint=exc.action_hint,
                    technical_detail=exc.message,
                )
                self._running = False
                raise  # Let PM2 watchdog see the non-zero exit

            except (AuthExpiredError, SessionInvalidError) as exc:
                logger.error(
                    "%s paused: %s — %s",
                    self.__class__.__name__,
                    exc.user_message,
                    exc.action_hint,
                )
                self._write_error_card("AUTH_ERROR", exc)
                audit_logger.log_error(
                    actor=self.__class__.__name__,
                    error_type=type(exc).__name__,
                    user_message=exc.user_message,
                    action_hint=exc.action_hint,
                    technical_detail=exc.message,
                )
                # Back off for 5 minutes before trying again
                time.sleep(300)

            except Exception as exc:
                # Catch-all: log and continue — never let an unexpected error
                # silently kill the watcher
                logger.exception(
                    "%s encountered an unexpected error. "
                    "The watcher will continue. Detail: %s",
                    self.__class__.__name__,
                    exc,
                )
                time.sleep(self.check_interval)

            else:
                time.sleep(self.check_interval)

    def stop(self) -> None:
        """Signal the run loop to exit cleanly on the next iteration."""
        self._running = False
        logger.info("%s stopping.", self.__class__.__name__)

    # ── Internal helpers ──────────────────────────────────────────────────────

    @with_retry(max_attempts=3, base_delay=2, max_delay=60)
    def _fetch_with_retry(self) -> list:
        """Wrap check_for_updates with automatic retry for transient failures."""
        return self.check_for_updates()

    def _tick(self) -> None:
        """Single polling cycle: fetch → deduplicate → write action files."""
        try:
            items = self._fetch_with_retry()
        except (NetworkError, RateLimitError) as exc:
            # Retries exhausted — log friendly message and skip this cycle
            logger.warning(
                "%s: %s %s",
                self.__class__.__name__,
                exc.user_message,
                exc.action_hint,
            )
            audit_logger.log_error(
                actor=self.__class__.__name__,
                error_type=type(exc).__name__,
                user_message=exc.user_message,
                action_hint=exc.action_hint,
                technical_detail=exc.message,
            )
            return

        new_items = []
        for item in items:
            try:
                event_id = self.get_event_id(item)
            except Exception as exc:
                logger.warning("Could not get ID for item — skipping: %s", exc)
                continue

            if event_id in self._processed_ids:
                logger.debug("Skipping already-processed item: %s", event_id)
                continue
            new_items.append((event_id, item))

        for event_id, item in new_items:
            try:
                path = self._write_action_file_atomic(item)
                self._processed_ids.add(event_id)
                audit_logger.log_action(
                    action_type="action_file_created",
                    actor=self.__class__.__name__,
                    target=str(path),
                    result="success",
                )
            except ParseError as exc:
                self._quarantine(item, exc)
            except WatcherError as exc:
                logger.warning(
                    "%s: could not process item — %s",
                    self.__class__.__name__,
                    exc.user_message,
                )

        # Persist the updated processed-ID set after each successful cycle
        self._save_state()

    def _write_action_file_atomic(self, item) -> Path:
        """
        Write the action file for *item* using a tmp-rename to prevent partial files.
        Returns the final file path.
        """
        self.needs_action.mkdir(parents=True, exist_ok=True)

        # Let the subclass build the content and target filename
        final_path = self._get_target_path(item)
        content = self.create_action_file(item)

        # If create_action_file already wrote the file, return its path
        if isinstance(content, Path):
            return content

        # Otherwise write via tmp-rename for atomicity
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            dir=self.needs_action,
            suffix=".tmp",
            delete=False,
        ) as tmp:
            tmp.write(content)
            tmp_path = Path(tmp.name)

        tmp_path.rename(final_path)
        return final_path

    def _get_target_path(self, item) -> Path:
        """Default target filename — subclasses may override."""
        return self.needs_action / f"{self.__class__.__name__}_{id(item)}.md"

    def _write_error_card(self, prefix: str, exc: WatcherError) -> None:
        """
        Write a human-readable error card to Needs_Action/ so the user sees
        the problem in Obsidian immediately.
        """
        try:
            self.needs_action.mkdir(parents=True, exist_ok=True)
            ts = int(time.time())
            card_path = self.needs_action / f"{prefix}_{self.__class__.__name__}_{ts}.md"
            card_path.write_text(
                f"---\ntype: error\nwatcher: {self.__class__.__name__}\n"
                f"error: {type(exc).__name__}\nstatus: needs_attention\n---\n\n"
                + exc.to_markdown(),
                encoding="utf-8",
            )
            logger.info("Error card written to %s", card_path)
        except OSError:
            logger.exception("Could not write error card to Needs_Action/.")

    def _quarantine(self, item, exc: ParseError) -> None:
        """Move a malformed item to a PARSE_ERROR_* card in Needs_Action/."""
        logger.warning(
            "%s: %s — %s",
            self.__class__.__name__,
            exc.user_message,
            exc.action_hint,
        )
        self._write_error_card("PARSE_ERROR", exc)
        audit_logger.log_error(
            actor=self.__class__.__name__,
            error_type="ParseError",
            user_message=exc.user_message,
            action_hint=exc.action_hint,
            technical_detail=exc.message,
        )

    def _save_state(self) -> None:
        """Persist the current processed-ID set."""
        state_manager.save_state(
            self.__class__.__name__,
            {"processed_ids": list(self._processed_ids)},
        )
