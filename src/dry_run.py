"""
src/dry_run.py — DRY_RUN safety guard for all external actions.

DRY_RUN=true (the default in .env.example) means the agent logs what it
*would* do without actually doing it. This is your safety net during setup
and testing — flip to DRY_RUN=false only when you're ready for live actions.
"""

import logging
import os

from src.audit import audit_logger

logger = logging.getLogger(__name__)


def is_dry_run() -> bool:
    """
    Return True when DRY_RUN env var is 'true' (case-insensitive).
    Defaults to True if the variable is not set — safe by default.
    """
    return os.getenv("DRY_RUN", "true").strip().lower() == "true"


def dry_run_guard(action_name: str, payload: dict, actor: str = "agent") -> bool:
    """
    Check the DRY_RUN flag before executing an external action.

    Usage:
        if dry_run_guard("email_send", {"to": addr, "subject": subj}):
            return  # skip real action in dry-run mode

        # proceed with real action here

    Returns:
        True  — DRY_RUN is active; caller should skip the real action.
        False — DRY_RUN is off; caller should proceed normally.
    """
    if not is_dry_run():
        return False

    # Log a friendly, visible dry-run notice
    payload_summary = ", ".join(f"{k}={v!r}" for k, v in list(payload.items())[:5])
    logger.info(
        "[DRY RUN] Would execute '%s' with: %s",
        action_name,
        payload_summary,
    )

    audit_logger.log_action(
        action_type=action_name,
        actor=actor,
        target=payload.get("target", payload.get("to", "unknown")),
        parameters=payload,
        approval_status="auto",
        approved_by="system",
        result="dry_run",
    )
    return True
