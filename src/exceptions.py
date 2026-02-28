"""
src/exceptions.py — Custom exception hierarchy for Digital FTE Agent.

Every exception carries:
  - message       : technical detail for logs
  - user_message  : plain-English explanation shown in Obsidian error cards
  - action_hint   : what the user should do to resolve the issue
  - context       : optional dict for structured audit logging
"""


class WatcherError(Exception):
    """Base exception for all Digital FTE agent errors."""

    # Subclasses override these defaults
    _default_user_message = "Something went wrong with the AI Employee."
    _default_action_hint = "Check the Logs/ folder in your Obsidian vault for details."

    def __init__(
        self,
        message: str,
        context: dict | None = None,
        user_message: str | None = None,
        action_hint: str | None = None,
    ):
        super().__init__(message)
        self.message = message
        self.context: dict = context or {}
        self.user_message: str = user_message or self._default_user_message
        self.action_hint: str = action_hint or self._default_action_hint

    def to_markdown(self) -> str:
        """Render a user-friendly Obsidian card for Needs_Action/."""
        return (
            f"## What happened\n{self.user_message}\n\n"
            f"## What to do\n{self.action_hint}\n\n"
            f"## Technical detail\n```\n{self.message}\n```\n"
        )

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}({self.message!r})"


# ──────────────────────────────────────────────
# Transient — safe to retry with backoff
# ──────────────────────────────────────────────

class NetworkError(WatcherError):
    """Temporary connection failure (timeout, DNS, etc.)."""

    _default_user_message = (
        "The AI Employee lost its internet connection for a moment."
    )
    _default_action_hint = (
        "No action needed — it will retry automatically. "
        "If this keeps happening, check your internet connection."
    )


class RateLimitError(WatcherError):
    """API rate limit hit; will back off and retry."""

    _default_user_message = (
        "An external service is temporarily busy and asked us to slow down."
    )
    _default_action_hint = (
        "The AI Employee will pause and retry shortly. No action needed."
    )

    def __init__(
        self,
        message: str,
        retry_after: int = 0,
        context: dict | None = None,
        **kwargs,
    ):
        super().__init__(message, context, **kwargs)
        self.retry_after = retry_after  # seconds suggested by the API


# ──────────────────────────────────────────────
# Authentication — halt and alert human
# ──────────────────────────────────────────────

class AuthExpiredError(WatcherError):
    """OAuth token or API key expired or revoked."""

    _default_user_message = (
        "Your login credentials for an external service have expired."
    )
    _default_action_hint = (
        "Re-authorise the app:\n"
        "1. Run `uv run python scripts/auth/<service>_auth.py`\n"
        "2. Follow the browser prompt to log in again\n"
        "3. The watcher will resume automatically."
    )


class SessionInvalidError(WatcherError):
    """Browser or WhatsApp Web session disconnected."""

    _default_user_message = (
        "The WhatsApp Web session has been disconnected or logged out."
    )
    _default_action_hint = (
        "Re-scan the WhatsApp QR code:\n"
        "1. Stop the WhatsApp watcher: `pm2 stop whatsapp_watcher`\n"
        "2. Delete the session folder set in WHATSAPP_SESSION_PATH\n"
        "3. Restart: `pm2 start whatsapp_watcher` and scan the QR code."
    )


# ──────────────────────────────────────────────
# Data — quarantine and alert
# ──────────────────────────────────────────────

class ParseError(WatcherError):
    """Could not parse an incoming item (email, CSV row, markdown)."""

    _default_user_message = (
        "The AI Employee received a message or file it could not understand."
    )
    _default_action_hint = (
        "Open the PARSE_ERROR_* file in your Needs_Action/ folder, "
        "review the raw content, and decide whether to handle it manually."
    )


class DuplicateItemError(WatcherError):
    """Item already processed; idempotency guard triggered."""

    _default_user_message = "This item was already handled — skipping."
    _default_action_hint = "No action needed."


# ──────────────────────────────────────────────
# Governance — never retry; require human
# ──────────────────────────────────────────────

class ConstitutionalBreachError(WatcherError):
    """Action violates the Digital FTE Constitution (Articles IV, XIII, XIV)."""

    _default_user_message = (
        "The AI Employee refused to perform an action that breaks its rules. "
        "This is a safety stop."
    )
    _default_action_hint = (
        "Review the breach notice in Needs_Action/BREACH_*.md. "
        "If the action is legitimate, approve it manually via Pending_Approval/."
    )


class ApprovalRequiredError(WatcherError):
    """Sensitive action attempted without human approval."""

    _default_user_message = (
        "This action requires your approval before it can proceed."
    )
    _default_action_hint = (
        "Open your Obsidian vault → Pending_Approval/ folder. "
        "Review the request, then move the file to Approved/ to proceed "
        "or to Rejected/ to cancel."
    )


# ──────────────────────────────────────────────
# System — watchdog will restart
# ──────────────────────────────────────────────

class VaultLockError(WatcherError):
    """Obsidian vault directory is locked or inaccessible."""

    _default_user_message = (
        "The AI Employee cannot write to your Obsidian vault right now."
    )
    _default_action_hint = (
        "Make sure Obsidian is not performing a sync or backup. "
        "If the problem persists, check file permissions on VAULT_PATH."
    )


class OrchestratorError(WatcherError):
    """Fatal orchestrator failure — PM2 watchdog will restart the process."""

    _default_user_message = (
        "The AI Employee's main process crashed and is restarting."
    )
    _default_action_hint = (
        "Check `logs/orchestrator.log` for the root cause. "
        "If restarts keep happening, run `pm2 logs orchestrator` for live output."
    )
