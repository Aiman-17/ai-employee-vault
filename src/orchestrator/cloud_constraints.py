"""
src/orchestrator/cloud_constraints.py — Constitutional breach guards for cloud agents.

Implements Article IX of the Digital FTE Constitution:
  - Cloud agent has DRAFT-ONLY authority (no direct send/payment execution)
  - Cloud agent must NEVER hold payment credentials
  - Cloud agent must NEVER access WhatsApp sessions

Called at orchestrator startup when AGENT_MODE=cloud.
If any assertion fails, raises ConstitutionalBreachError and the orchestrator
halts with a clear error message — the PM2 watchdog will log but NOT restart
until the violation is corrected.
"""

from __future__ import annotations

import logging
import os
from pathlib import Path

from src.exceptions import ConstitutionalBreachError

logger = logging.getLogger(__name__)

# Direct-send / execute actions blocked for cloud agents (Article IX)
_BLOCKED_CLOUD_ACTIONS: frozenset[str] = frozenset(
    {
        "send_email",
        "send_payment",
        "execute_payment",
        "whatsapp_send",
        "bank_transfer",
        "invoice_post",
        "payment_create",
    }
)


def assert_draft_only(action_type: str) -> None:
    """
    Raise ConstitutionalBreachError if *action_type* is a direct-send or
    execute action.

    Cloud agents may only draft proposals and write approval requests.
    Local agents approve and execute the final action.
    """
    if action_type in _BLOCKED_CLOUD_ACTIONS:
        raise ConstitutionalBreachError(
            f"Cloud agent attempted '{action_type}' — Constitution Article IX breach.",
            user_message=(
                f"The Cloud agent tried to execute '{action_type}' directly. "
                "Cloud agents may only create drafts and approval requests."
            ),
            action_hint=(
                "This action has been blocked and logged. "
                "Switch to Local mode (AGENT_MODE=local) to execute send/payment actions."
            ),
        )


def assert_no_payment_credentials() -> None:
    """
    Raise ConstitutionalBreachError if BANK_API_TOKEN is present.

    Payment credentials must NEVER be available on the cloud VM.
    """
    if os.getenv("BANK_API_TOKEN"):
        raise ConstitutionalBreachError(
            "BANK_API_TOKEN is set in cloud environment — Constitution Article IX breach.",
            user_message=(
                "Payment credentials were found in the Cloud agent's environment. "
                "This is a security violation: cloud agents must never hold banking credentials."
            ),
            action_hint=(
                "Remove BANK_API_TOKEN from the cloud VM .env file. "
                "Banking actions must be executed by the Local agent only."
            ),
        )


def assert_no_whatsapp_session() -> None:
    """
    Raise ConstitutionalBreachError if a WhatsApp session directory exists.

    WhatsApp sessions store authentication credentials and must stay on the
    Local machine. Cloud agents communicating via WhatsApp is a constitutional
    violation.
    """
    session_path = os.getenv("WHATSAPP_SESSION_PATH", "")
    if session_path and Path(session_path).exists():
        raise ConstitutionalBreachError(
            f"WhatsApp session found at {session_path!r} on cloud VM — Constitution Article IX breach.",
            user_message=(
                "A WhatsApp session directory was found on the Cloud agent's machine. "
                "Cloud agents must never hold WhatsApp sessions."
            ),
            action_hint=(
                "Remove WHATSAPP_SESSION_PATH from the cloud VM .env file "
                "and delete the session directory from the cloud VM."
            ),
        )


def enforce_all_cloud_constraints() -> None:
    """
    Run all cloud constraint assertions.

    Called at orchestrator startup when AGENT_MODE=cloud.
    Raises ConstitutionalBreachError on the first violation detected — the
    orchestrator must not start if any constraint is violated.
    """
    logger.info("[cloud_constraints] Enforcing Article IX constitutional constraints...")
    assert_no_payment_credentials()
    assert_no_whatsapp_session()
    logger.info("[cloud_constraints] All cloud constraints satisfied — proceeding as draft-only agent.")
