"""
src/audit/audit_logger.py — Structured audit log writer.

Every action the AI Employee takes is logged to VAULT_PATH/Logs/YYYY-MM-DD.json
(one file per day, append mode). Logs are human-readable in Obsidian via the
JSON viewer plugin and machine-readable for compliance review.

Retention: 90 days. Old log rotation is the user's responsibility for now;
a future task can automate it via the weekly CEO Briefing skill.
"""

import json
import logging
import os
from datetime import datetime, timezone
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)


def _log_dir() -> Path:
    vault = os.getenv("VAULT_PATH", "")
    if not vault:
        fallback = Path("logs")
        fallback.mkdir(exist_ok=True)
        return fallback
    return Path(vault) / "Logs"


def log_action(
    action_type: str,
    actor: str,
    target: str,
    parameters: dict | None = None,
    approval_status: str = "auto",
    approved_by: str = "system",
    result: str = "success",
    error_detail: str | None = None,
) -> None:
    """
    Append a structured audit entry to today's log file.

    Args:
        action_type:     What kind of action (e.g. "email_send", "file_move",
                         "process_restart", "approval_created").
        actor:           Who performed it (e.g. "gmail_watcher", "claude_code").
        target:          What was acted upon (e.g. email address, file path).
        parameters:      Arbitrary key-value context for the action.
        approval_status: "auto", "approved", "pending", "rejected".
        approved_by:     "human", "system", or the approver's identifier.
        result:          "success", "failure", "skipped", "dry_run".
        error_detail:    Plain-English error description if result == "failure".
    """
    entry = {
        "timestamp": datetime.now(tz=timezone.utc).isoformat(),
        "action_type": action_type,
        "actor": actor,
        "target": target,
        "parameters": parameters or {},
        "approval_status": approval_status,
        "approved_by": approved_by,
        "result": result,
    }
    if error_detail:
        entry["error_detail"] = error_detail

    log_dir = _log_dir()
    today = datetime.now(tz=timezone.utc).strftime("%Y-%m-%d")
    log_file = log_dir / f"{today}.json"

    try:
        log_dir.mkdir(parents=True, exist_ok=True)

        # Append as newline-delimited JSON (one object per line) so the file
        # remains valid even if opened mid-write and is easy to tail/grep.
        def _default(obj):
            if hasattr(obj, "isoformat"):
                return obj.isoformat()
            return str(obj)

        with log_file.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(entry, ensure_ascii=False, default=_default) + "\n")

    except OSError as exc:
        # Logging must NEVER crash the watcher — fall back to stderr.
        logger.error(
            "Could not write audit log to %s: %s. "
            "Action %r by %r will not be recorded in the vault.",
            log_file,
            exc,
            action_type,
            actor,
        )
        # Print directly so the PM2 log still captures it
        print(f"[AUDIT FALLBACK] {json.dumps(entry)}", flush=True)


def log_error(
    actor: str,
    error_type: str,
    user_message: str,
    action_hint: str,
    technical_detail: str = "",
) -> None:
    """
    Log an error event. Convenience wrapper around log_action.

    Also emits a formatted warning through the standard logger so it appears
    in PM2 logs in a readable way, not just as a JSON blob.
    """
    logger.warning(
        "[%s] %s — %s",
        actor,
        user_message,
        action_hint,
    )
    log_action(
        action_type="error",
        actor=actor,
        target=error_type,
        parameters={"user_message": user_message, "action_hint": action_hint},
        result="failure",
        error_detail=technical_detail,
    )
