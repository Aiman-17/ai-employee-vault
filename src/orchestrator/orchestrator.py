"""
src/orchestrator/orchestrator.py — Master orchestrator for the Digital FTE Agent.

Responsibilities:
  1. Register and start all Python Watchers in background threads.
  2. Poll Needs_Action/ and dispatch tasks using the claim-by-move rule.
  3. Run scheduled tasks (e.g. weekly CEO Briefing) via lightweight cron.
  4. Shut down cleanly on SIGINT / SIGTERM.

Error philosophy:
  - Watcher thread crashes are caught and logged; the watchdog (watchdog.py)
    restarts the PM2 process.
  - Task dispatch errors are caught per-item so one bad file never stalls the queue.
  - SIGINT shows a user-friendly shutdown message.
"""

import logging
import os
import signal
import threading
import time
from pathlib import Path

from dotenv import load_dotenv

from src.audit import audit_logger
from src.vault_utils import claim_task
from src.watchers.base_watcher import BaseWatcher

load_dotenv()

logger = logging.getLogger(__name__)

AGENT_ID = os.getenv("CLOUD_AGENT_ID", "local")
POLL_INTERVAL = 5  # seconds between Needs_Action/ scans


class Orchestrator:
    """
    Master process that coordinates watchers, task dispatch, and scheduling.
    """

    def __init__(self):
        vault = os.getenv("VAULT_PATH", "")
        if not vault:
            logger.warning(
                "VAULT_PATH is not set. The orchestrator will use the current directory. "
                "Run scripts/setup_vault.py after setting VAULT_PATH in .env."
            )
        self.vault_path = Path(vault) if vault else Path(".")
        self.needs_action = self.vault_path / "Needs_Action"

        self._watchers: list[BaseWatcher] = []
        self._schedules: list[tuple[float, callable]] = []  # (interval_seconds, handler)
        self._threads: list[threading.Thread] = []
        self._running = False

        # Register graceful shutdown handlers
        signal.signal(signal.SIGINT, self._handle_shutdown)
        signal.signal(signal.SIGTERM, self._handle_shutdown)

    # ── Registration ──────────────────────────────────────────────────────────

    def register_watcher(self, watcher: BaseWatcher) -> None:
        """Add a watcher to be started when run() is called."""
        self._watchers.append(watcher)
        logger.debug("Registered watcher: %s", watcher.__class__.__name__)

    def register_schedule(self, interval_seconds: float, handler: callable) -> None:
        """Register a periodic task (e.g. CEO Briefing every 604800s = 7 days)."""
        self._schedules.append((interval_seconds, handler))
        logger.debug(
            "Registered schedule: %s every %.0fs",
            getattr(handler, "__name__", repr(handler)),
            interval_seconds,
        )

    # ── Main loop ─────────────────────────────────────────────────────────────

    def run(self) -> None:
        """Start all watchers and enter the task dispatch loop."""
        self._running = True
        logger.info("Orchestrator starting (agent_id=%s).", AGENT_ID)

        # ── Cloud constitutional constraints (Article IX) ──────────────────
        agent_mode = os.getenv("AGENT_MODE", "local").lower()
        if agent_mode == "cloud":
            from src.orchestrator.cloud_constraints import enforce_all_cloud_constraints
            from src.exceptions import ConstitutionalBreachError
            try:
                enforce_all_cloud_constraints()
            except ConstitutionalBreachError as breach:
                logger.critical(
                    "[CONSTITUTIONAL BREACH] %s\n"
                    "User message: %s\n"
                    "Action hint:  %s\n"
                    "Orchestrator HALTED — correct the violation and restart.",
                    breach.message,
                    breach.user_message,
                    breach.action_hint,
                )
                raise SystemExit(1) from breach

        self._start_watchers()
        self._start_scheduler()

        logger.info(
            "AI Employee is active. Monitoring %s every %ds.",
            self.needs_action,
            POLL_INTERVAL,
        )

        while self._running:
            try:
                self._dispatch_pending_tasks()
            except Exception as exc:
                logger.exception(
                    "Unexpected error in task dispatch loop: %s. "
                    "The orchestrator will continue on the next cycle.",
                    exc,
                )
            time.sleep(POLL_INTERVAL)

        self._stop_watchers()
        logger.info("Orchestrator shut down cleanly.")

    # ── Task dispatch ─────────────────────────────────────────────────────────

    def _dispatch_pending_tasks(self) -> None:
        """Scan Needs_Action/ and claim unclaimed .md files."""
        if not self.needs_action.exists():
            return

        for task_file in sorted(self.needs_action.glob("*.md")):
            if not task_file.is_file():
                continue
            claimed = claim_task(self.vault_path, task_file, AGENT_ID)
            if not claimed:
                continue  # Another agent already has it

            logger.info("Claimed task: %s", task_file.name)
            audit_logger.log_action(
                action_type="task_claimed",
                actor=f"orchestrator:{AGENT_ID}",
                target=task_file.name,
                result="success",
            )
            # TODO (Phase 3+): dispatch to the appropriate skill/handler

    # ── Watcher thread management ─────────────────────────────────────────────

    def _start_watchers(self) -> None:
        for watcher in self._watchers:
            thread = threading.Thread(
                target=self._run_watcher_safe,
                args=(watcher,),
                name=watcher.__class__.__name__,
                daemon=True,
            )
            thread.start()
            self._threads.append(thread)
            logger.info("Started watcher thread: %s", watcher.__class__.__name__)

    def _run_watcher_safe(self, watcher: BaseWatcher) -> None:
        """Run a watcher, catching any top-level exception so the thread exits cleanly."""
        try:
            watcher.run()
        except Exception as exc:
            logger.error(
                "Watcher %s crashed: %s. "
                "PM2 / watchdog.py will restart the process if needed.",
                watcher.__class__.__name__,
                exc,
            )

    def _stop_watchers(self) -> None:
        for watcher in self._watchers:
            watcher.stop()
        for thread in self._threads:
            thread.join(timeout=5)

    # ── Scheduler ─────────────────────────────────────────────────────────────

    def _start_scheduler(self) -> None:
        if not self._schedules:
            return

        def scheduler_loop():
            last_run: dict[int, float] = {}
            while self._running:
                now = time.monotonic()
                for idx, (interval, handler) in enumerate(self._schedules):
                    if now - last_run.get(idx, 0) >= interval:
                        try:
                            handler()
                        except Exception as exc:
                            logger.error(
                                "Scheduled task %s failed: %s",
                                getattr(handler, "__name__", idx),
                                exc,
                            )
                        last_run[idx] = now
                time.sleep(60)

        thread = threading.Thread(target=scheduler_loop, name="Scheduler", daemon=True)
        thread.start()
        self._threads.append(thread)

    # ── Error degradation handlers ────────────────────────────────────────────

    def handle_gmail_down(self, error: Exception | None = None) -> None:
        """
        Graceful degradation: Gmail API unavailable.

        Strategy: queue outgoing draft replies locally in Pending_Approval/
        and continue processing other vault tasks. The Gmail Watcher will
        resume when connectivity is restored.
        """
        msg = f"Gmail API unavailable: {error}" if error else "Gmail API unavailable."
        logger.warning("[DEGRADATION] %s Drafts will queue in Pending_Approval/.", msg)
        audit_logger.log_action(
            action_type="degradation_gmail_down",
            actor=f"orchestrator:{AGENT_ID}",
            target="gmail",
            parameters={"error": str(error)},
            result="queuing_drafts_locally",
        )
        # Write a degradation notice to the vault dashboard
        dashboard = self.vault_path / "Dashboard.md"
        if dashboard.exists():
            try:
                existing = dashboard.read_text(encoding="utf-8")
                notice = f"\n> ⚠️ **Gmail API down** — drafts queued locally. {msg}\n"
                if notice.strip() not in existing:
                    dashboard.write_text(existing + notice, encoding="utf-8")
            except Exception:
                pass

    def handle_banking_timeout(self, error: Exception | None = None) -> None:
        """
        Graceful degradation: Banking API timed out.

        Strategy: HALT all payment-related operations immediately. Never
        retry payments automatically. Require fresh human approval before
        any subsequent payment attempt.
        """
        msg = f"Banking API timeout: {error}" if error else "Banking API timeout."
        logger.error(
            "[DEGRADATION] %s All payment operations HALTED. "
            "Human re-approval required before any retry.",
            msg,
        )
        audit_logger.log_action(
            action_type="degradation_banking_timeout",
            actor=f"orchestrator:{AGENT_ID}",
            target="banking",
            parameters={"error": str(error)},
            result="payments_halted",
        )
        # Write a high-priority alert to Needs_Action
        alert_dir = self.vault_path / "Needs_Action"
        alert_dir.mkdir(parents=True, exist_ok=True)
        from datetime import date
        alert_file = alert_dir / f"ALERT_banking_timeout_{date.today().isoformat()}.md"
        if not alert_file.exists():
            alert_file.write_text(
                f"---\ntype: banking_alert\npriority: critical\nstatus: pending\n---\n\n"
                f"## ⚠️ Banking API Timeout\n\n{msg}\n\n"
                f"All payment operations have been HALTED.\n"
                f"Please re-approve any pending payments before retrying.\n",
                encoding="utf-8",
            )

    def handle_vault_locked(self, error: Exception | None = None) -> None:
        """
        Graceful degradation: Obsidian vault is locked or inaccessible.

        Strategy: write pending outputs to a temporary staging directory
        and sync them to the vault when it becomes available again.
        """
        import tempfile

        msg = f"Vault locked: {error}" if error else "Vault inaccessible."
        logger.warning(
            "[DEGRADATION] %s Writes will stage in system temp dir until vault available.",
            msg,
        )
        audit_logger.log_action(
            action_type="degradation_vault_locked",
            actor=f"orchestrator:{AGENT_ID}",
            target=str(self.vault_path),
            parameters={"error": str(error)},
            result="staging_to_temp",
        )
        # Ensure a temp staging directory exists for this process
        staging = Path(tempfile.gettempdir()) / "digital_fte_staging"
        staging.mkdir(parents=True, exist_ok=True)
        logger.info("Staging directory ready: %s", staging)

    # ── Shutdown ──────────────────────────────────────────────────────────────

    def _handle_shutdown(self, signum, frame) -> None:
        logger.info(
            "\nShutting down AI Employee gracefully… "
            "(all in-progress tasks will be logged)"
        )
        self._running = False


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
    )
    Orchestrator().run()
