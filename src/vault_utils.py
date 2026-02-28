"""
src/vault_utils.py — Vault file operations with graceful error handling.

All functions that write to the vault use atomic moves or lock files to
prevent corruption. Errors produce clear messages so the user knows
exactly what went wrong and how to fix it.
"""

import logging
import os
import sys
import tempfile
import time
from pathlib import Path

# fcntl is POSIX-only; on Windows we fall back to a no-op lock
if sys.platform != "win32":
    import fcntl as _fcntl  # type: ignore[import]
else:
    _fcntl = None  # type: ignore[assignment]

from dotenv import load_dotenv

from src.audit import audit_logger
from src.exceptions import ApprovalRequiredError, VaultLockError

load_dotenv()

logger = logging.getLogger(__name__)

DASHBOARD_LOCK_TIMEOUT = 5  # seconds


def _vault() -> Path:
    vault = os.getenv("VAULT_PATH", "")
    if not vault:
        logger.warning(
            "VAULT_PATH is not set — vault operations will use the current directory. "
            "Set VAULT_PATH in .env and run scripts/setup_vault.py."
        )
        return Path(".")
    return Path(vault)


# ── File movement ─────────────────────────────────────────────────────────────

def move_file(src: Path, dst: Path) -> None:
    """
    Atomically move *src* to *dst*.

    Gracefully handles:
      - Missing source: logs a warning instead of crashing.
      - Permission errors: clear message + hint to check file permissions.
    """
    if not src.exists():
        logger.warning(
            "move_file: source does not exist — %s. "
            "It may have already been moved by another process.",
            src,
        )
        return

    try:
        dst.parent.mkdir(parents=True, exist_ok=True)
        os.replace(src, dst)
        logger.debug("Moved %s → %s", src.name, dst.parent.name)
    except PermissionError as exc:
        logger.error(
            "Cannot move %s to %s: permission denied. "
            "Check that no other application has the file locked. "
            "Detail: %s",
            src,
            dst,
            exc,
        )
        raise VaultLockError(
            str(exc),
            user_message=f"Could not move '{src.name}' — another app may have it open.",
            action_hint="Close Obsidian or any file explorer windows and try again.",
        ) from exc


# ── Dashboard updates ─────────────────────────────────────────────────────────

def update_dashboard(vault_path: Path, entry: str) -> None:
    """
    Append *entry* to the '## Recent Activity' section of Dashboard.md.

    Respects the single-writer rule:
      - AGENT_MODE=local  → acquire a lock file before writing.
      - AGENT_MODE=cloud  → write an update card to Updates/ instead.

    If the dashboard file is missing, logs a user-friendly warning and skips.
    """
    agent_mode = os.getenv("AGENT_MODE", "local").lower()

    if agent_mode == "cloud":
        _write_cloud_update(vault_path, entry)
        return

    dashboard = vault_path / "Dashboard.md"
    if not dashboard.exists():
        logger.warning(
            "Dashboard.md not found at %s. "
            "Run scripts/setup_vault.py to create it.",
            dashboard,
        )
        return

    lock_path = vault_path / ".dashboard.lock"

    try:
        with open(lock_path, "w") as lock_fh:
            _acquire_lock(lock_fh, lock_path)
            _append_recent_activity(dashboard, entry)
    except VaultLockError:
        raise
    except OSError as exc:
        logger.error(
            "Could not update Dashboard.md: %s. "
            "The entry '%s' was NOT recorded. Check vault permissions.",
            exc,
            entry[:80],
        )


def _acquire_lock(lock_fh, lock_path: Path) -> None:
    """Try to acquire an exclusive file lock; raise VaultLockError on timeout.

    On Windows, fcntl is not available so this is a no-op — single-process
    access is safe enough for local development.  For multi-process safety on
    Windows, set AGENT_MODE=cloud so updates go to the Updates/ queue instead.
    """
    if _fcntl is None:
        # Windows: no kernel file locking — proceed without lock
        return

    deadline = time.monotonic() + DASHBOARD_LOCK_TIMEOUT
    while True:
        try:
            _fcntl.flock(lock_fh, _fcntl.LOCK_EX | _fcntl.LOCK_NB)
            return
        except BlockingIOError:
            if time.monotonic() >= deadline:
                raise VaultLockError(
                    f"Dashboard lock timeout after {DASHBOARD_LOCK_TIMEOUT}s",
                    user_message="Dashboard.md is busy — another process is writing to it.",
                    action_hint=(
                        "This usually resolves itself. If it persists, "
                        f"delete {lock_path} manually."
                    ),
                )
            time.sleep(0.1)


def _append_recent_activity(dashboard: Path, entry: str) -> None:
    """Insert a timestamped bullet under '## Recent Activity' in Dashboard.md."""
    text = dashboard.read_text(encoding="utf-8")
    timestamp = time.strftime("%Y-%m-%d %H:%M")
    bullet = f"- [{timestamp}] {entry}"

    if "## Recent Activity" in text:
        text = text.replace(
            "## Recent Activity",
            f"## Recent Activity\n{bullet}",
            1,
        )
    else:
        text += f"\n\n## Recent Activity\n{bullet}\n"

    dashboard.write_text(text, encoding="utf-8")
    logger.debug("Dashboard updated: %s", bullet)


def _write_cloud_update(vault_path: Path, entry: str) -> None:
    """Cloud agents write updates here; Local merges them into Dashboard."""
    updates_dir = vault_path / "Updates"
    updates_dir.mkdir(parents=True, exist_ok=True)
    ts = int(time.time())
    card = updates_dir / f"dashboard_update_{ts}.md"
    card.write_text(
        f"---\ntype: dashboard_update\ncreated: {time.strftime('%Y-%m-%dT%H:%M:%SZ')}\n---\n\n"
        f"{entry}\n",
        encoding="utf-8",
    )
    logger.debug("Cloud dashboard update queued: %s", card.name)


# ── HITL approval workflow ────────────────────────────────────────────────────

def create_pending_approval(
    vault_path: Path,
    action_type: str,
    payload: dict,
    plan_ref: str = "",
    expires_hours: int = 24,
) -> Path:
    """
    Write a Pending_Approval file and return its path.

    The user moves this file to Approved/ (or Rejected/) in Obsidian to
    authorise or cancel the action.
    """
    pending_dir = vault_path / "Pending_Approval"
    pending_dir.mkdir(parents=True, exist_ok=True)

    ts = time.strftime("%Y-%m-%d_%H-%M-%S")
    filename = f"{action_type.upper()}_{ts}.md"
    path = pending_dir / filename

    expiry = time.strftime(
        "%Y-%m-%dT%H:%M:%SZ",
        time.gmtime(time.time() + expires_hours * 3600),
    )

    lines = [
        "---",
        f"type: approval_request",
        f"action: {action_type}",
        f"plan_ref: {plan_ref}",
        f"created: {time.strftime('%Y-%m-%dT%H:%M:%SZ')}",
        f"expires: {expiry}",
        "status: pending",
        "---",
        "",
        f"## Action: {action_type}",
        "",
    ]
    for key, value in payload.items():
        lines.append(f"- **{key}**: {value}")

    lines += [
        "",
        "## To Approve",
        "Move this file to the `Approved/` folder in Obsidian.",
        "",
        "## To Reject",
        "Move this file to the `Rejected/` folder in Obsidian.",
        "",
        f"> This request expires at {expiry}.",
    ]

    path.write_text("\n".join(lines), encoding="utf-8")
    logger.info("Approval request created: %s", path.name)

    audit_logger.log_action(
        action_type="approval_created",
        actor="vault_utils",
        target=str(path),
        parameters={"action_type": action_type, **payload},
        approval_status="pending",
        approved_by="pending",
        result="success",
    )
    return path


def check_approved(vault_path: Path, approval_filename: str) -> bool:
    """Return True if the given approval file exists in the Approved/ folder."""
    return (vault_path / "Approved" / approval_filename).exists()


# ── Claim-by-move (anti-double-processing) ────────────────────────────────────

def claim_task(vault_path: Path, task_file: Path, agent_id: str) -> bool:
    """
    Atomically claim *task_file* by moving it from Needs_Action/ to
    In_Progress/<agent_id>/. Returns True if the claim succeeded.

    If another agent already claimed the file, returns False silently —
    the caller should skip this item without logging an error.
    """
    target_dir = vault_path / "In_Progress" / agent_id
    target_dir.mkdir(parents=True, exist_ok=True)
    target = target_dir / task_file.name

    try:
        task_file.rename(target)
        logger.debug("Claimed %s → In_Progress/%s/", task_file.name, agent_id)
        return True
    except FileNotFoundError:
        # Another agent got there first — normal race condition, not an error
        logger.debug(
            "Could not claim %s — already taken by another agent.", task_file.name
        )
        return False
    except OSError as exc:
        logger.warning(
            "Failed to claim %s: %s. Will skip this item.",
            task_file.name,
            exc,
        )
        return False


# ── Dashboard lock (TTL-based, cross-agent) ───────────────────────────────────

_DASHBOARD_LOCK_FILENAME = ".dashboard.lock"
_DASHBOARD_LOCK_TTL = 5  # seconds


def acquire_dashboard_lock(vault_path: Path, agent_id: str = "agent") -> bool:
    """
    Acquire a TTL-based dashboard lock.

    Creates ``<vault_path>/.dashboard.lock`` containing the *agent_id* and an
    expiry timestamp (now + 5 s).  Returns ``True`` on success.

    Returns ``False`` — without raising — when:
    - The lock file already exists **and** has not yet expired.

    Expired locks are silently removed before re-acquisition so a crashed
    agent never blocks the dashboard indefinitely.
    """
    lock_path = vault_path / _DASHBOARD_LOCK_FILENAME
    now = time.time()

    # Remove stale lock if it has expired
    if lock_path.exists():
        try:
            parts = lock_path.read_text(encoding="utf-8").strip().splitlines()
            expiry = float(parts[-1]) if parts else 0.0
            if now < expiry:
                logger.debug(
                    "Dashboard lock held by %s, expires in %.1fs.",
                    parts[0] if parts else "unknown",
                    expiry - now,
                )
                return False
            # Expired — remove it
            lock_path.unlink(missing_ok=True)
            logger.debug("Removed expired dashboard lock.")
        except (ValueError, OSError):
            # Corrupt or unreadable lock → remove and continue
            lock_path.unlink(missing_ok=True)

    # Write new lock
    expiry = now + _DASHBOARD_LOCK_TTL
    try:
        lock_path.write_text(f"{agent_id}\n{expiry}", encoding="utf-8")
        logger.debug("Dashboard lock acquired by %s (expires %.1fs).", agent_id, expiry)
        return True
    except OSError as exc:
        logger.warning("Could not write dashboard lock: %s", exc)
        return False


def release_dashboard_lock(vault_path: Path) -> None:
    """
    Release the dashboard lock by removing the lock file.

    Safe to call even if the lock does not exist (e.g. it already expired).
    """
    lock_path = vault_path / _DASHBOARD_LOCK_FILENAME
    try:
        lock_path.unlink(missing_ok=True)
        logger.debug("Dashboard lock released.")
    except OSError as exc:
        logger.warning("Could not remove dashboard lock: %s", exc)
