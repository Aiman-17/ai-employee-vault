"""
src/orchestrator/watchdog.py — Process health monitor for Digital FTE Agent.

Checks all PM2-managed watcher processes every 60 seconds.
Restarts any that have crashed, writes a PID file, and logs the restart
in the Obsidian vault so the user knows what happened.

This is a fallback for environments where PM2 is not available.
When running under PM2, PM2 itself handles auto-restart — this script
provides the same guarantee for bare-Python deployments.
"""

import logging
import os
import subprocess
import sys
import time
from pathlib import Path

from dotenv import load_dotenv

from src.audit import audit_logger

load_dotenv()

logger = logging.getLogger(__name__)

# Processes that should always be running
MANAGED_PROCESSES = {
    "orchestrator": [sys.executable, "-m", "src.orchestrator.orchestrator"],
    "filesystem_watcher": [sys.executable, "-m", "src.watchers.filesystem_watcher"],
    "gmail_watcher": [sys.executable, "-m", "src.watchers.gmail_watcher"],
    "whatsapp_watcher": [sys.executable, "-m", "src.watchers.whatsapp_watcher"],
    "finance_watcher": [sys.executable, "-m", "src.watchers.finance_watcher"],
}

PID_DIR = Path(os.getenv("TMPDIR", "/tmp"))
CHECK_INTERVAL = 60  # seconds


def _pid_file(name: str) -> Path:
    return PID_DIR / f"digital_fte_{name}.pid"


def _is_running(name: str) -> bool:
    """Return True if the process recorded in the PID file is still alive."""
    pid_path = _pid_file(name)
    if not pid_path.exists():
        return False
    try:
        pid = int(pid_path.read_text().strip())
        # Kill 0 checks existence without sending a signal
        os.kill(pid, 0)
        return True
    except (ValueError, ProcessLookupError, PermissionError):
        return False


def _start_process(name: str, cmd: list[str]) -> None:
    """Launch *cmd* as a detached subprocess and record its PID."""
    try:
        proc = subprocess.Popen(
            cmd,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            start_new_session=True,
        )
        _pid_file(name).write_text(str(proc.pid))
        logger.info("Started %s (PID %d).", name, proc.pid)

        audit_logger.log_action(
            action_type="process_restart",
            actor="watchdog",
            target=name,
            parameters={"pid": proc.pid, "cmd": " ".join(cmd)},
            result="success",
        )

    except FileNotFoundError as exc:
        logger.error(
            "Cannot start %s — executable not found: %s. "
            "Make sure you ran `uv sync` to install dependencies.",
            name,
            exc,
        )
    except OSError as exc:
        logger.error(
            "Failed to start %s: %s. "
            "Check that the script path is correct and the file exists.",
            name,
            exc,
        )


def check_and_restart() -> None:
    """One pass: check all managed processes and restart any that are down."""
    for name, cmd in MANAGED_PROCESSES.items():
        if not _is_running(name):
            logger.warning(
                "%s is not running — restarting. "
                "Check logs/%s.log if this keeps happening.",
                name,
                name,
            )
            _start_process(name, cmd)


def run() -> None:
    """Run the watchdog loop indefinitely."""
    logger.info("Watchdog started. Monitoring %d processes.", len(MANAGED_PROCESSES))
    while True:
        try:
            check_and_restart()
        except Exception as exc:
            logger.exception("Unexpected watchdog error: %s", exc)
        time.sleep(CHECK_INTERVAL)


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [watchdog] %(levelname)s: %(message)s",
    )
    run()
