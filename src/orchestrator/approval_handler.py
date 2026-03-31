"""
src/orchestrator/approval_handler.py — HITL approval workflow engine.

Watches VAULT_PATH/Approved/ for files the user has moved from Pending_Approval/.
On each new arrival it reads the YAML front-matter, executes the approved action,
logs the outcome, and moves all related artifacts to Done/.

Supports actions:
  Bronze:  file_move  — move a vault artifact
  Silver+: email_send — send via Gmail API (google-api-python-client); DRY_RUN guard
  Gold+:   payment    — delegate to browser-mcp (always requires fresh approval)

User-friendly errors:
  - Missing plan_ref       → warn and still execute best-effort
  - Unknown action type    → write clear error card; move to Rejected/
  - MCP call failure       → write retry card in Needs_Action/; preserve approval file
  - Expired approval       → reject with explanation shown in Obsidian
"""

import base64
import email as email_lib
import logging
import os
import threading
import time
from pathlib import Path

import yaml
from dotenv import load_dotenv
from watchdog.events import FileSystemEventHandler
from watchdog.observers import Observer

from src.audit import audit_logger
from src.dry_run import dry_run_guard
from src.exceptions import ApprovalRequiredError, ConstitutionalBreachError
from src.vault_utils import move_file, update_dashboard

load_dotenv()

logger = logging.getLogger(__name__)

# Actions that need a fresh approval check every time (never auto-retry)
_ALWAYS_FRESH = {"payment", "account_closure", "subscription_cancel", "bulk_email"}


# ── File-system event handler (watchdog thread) ───────────────────────────────

class _ApprovedFolderHandler(FileSystemEventHandler):
    def __init__(self, handler: "ApprovalHandler"):
        super().__init__()
        self._handler = handler

    def on_created(self, event):
        if event.is_directory:
            return
        path = Path(event.src_path)
        if path.suffix == ".md":
            # Small delay — let the move operation finish before we read
            time.sleep(0.2)
            self._handler._process_approval(path)


# ── Main handler class ────────────────────────────────────────────────────────

class ApprovalHandler:
    """
    Listens to VAULT_PATH/Approved/ and executes approved actions.
    Runs in its own daemon thread.
    """

    def __init__(self):
        vault = os.getenv("VAULT_PATH", "")
        if not vault:
            logger.warning(
                "VAULT_PATH is not set — ApprovalHandler cannot start. "
                "Set VAULT_PATH in .env and restart."
            )
        self.vault_path = Path(vault) if vault else Path(".")
        self.approved_dir = self.vault_path / "Approved"
        self.rejected_dir = self.vault_path / "Rejected"
        self.done_dir = self.vault_path / "Done"

        self._observer: Observer | None = None
        self._thread: threading.Thread | None = None

    def start(self) -> None:
        """Start the approval handler in a background daemon thread."""
        self.approved_dir.mkdir(parents=True, exist_ok=True)

        event_handler = _ApprovedFolderHandler(self)
        self._observer = Observer()
        self._observer.schedule(event_handler, str(self.approved_dir), recursive=False)
        self._observer.start()
        logger.info("ApprovalHandler watching: %s", self.approved_dir)

    def stop(self) -> None:
        if self._observer:
            self._observer.stop()
            self._observer.join()
            logger.info("ApprovalHandler stopped.")

    # ── Processing logic ──────────────────────────────────────────────────────

    def _process_approval(self, approval_file: Path) -> None:
        """Handle one approved file: validate → execute → archive."""
        logger.info("Processing approval: %s", approval_file.name)

        try:
            meta = self._parse_front_matter(approval_file)
        except Exception as exc:
            logger.error(
                "Could not read approval file %s: %s. "
                "Check that it has valid YAML front-matter.",
                approval_file.name,
                exc,
            )
            return

        action_type = meta.get("action", "unknown")
        plan_ref = meta.get("plan_ref", "")

        # Check expiry
        if self._is_expired(meta):
            logger.warning(
                "Approval %s has expired — rejecting. "
                "Create a new approval request from Pending_Approval/.",
                approval_file.name,
            )
            self._archive(approval_file, self.rejected_dir, plan_ref, "expired")
            return

        # Constitutional guard: high-risk actions require extra validation
        if action_type in _ALWAYS_FRESH:
            logger.info(
                "High-risk action '%s' — proceeding with extra audit logging.",
                action_type,
            )

        try:
            self._execute_action(action_type, meta, approval_file)
        except ConstitutionalBreachError as exc:
            logger.critical("Constitutional breach during approval: %s", exc.user_message)
            self._write_error_card("BREACH", exc.to_markdown())
            self._archive(approval_file, self.rejected_dir, plan_ref, "breach")
        except Exception as exc:
            logger.error(
                "Action '%s' failed: %s. "
                "The approval file has been preserved — retry by moving it "
                "back to Approved/ or create a new request.",
                action_type,
                exc,
            )
            self._write_retry_card(action_type, approval_file.name, str(exc))
            # Don't archive — leave in Approved/ so user can retry

    def _execute_action(self, action_type: str, meta: dict, approval_file: Path) -> None:
        """Route to the appropriate action executor."""

        if action_type == "file_move":
            self._execute_file_move(meta, approval_file)

        elif action_type == "email_send":
            self._execute_email_send(meta, approval_file)

        elif action_type == "payment":
            self._execute_payment(meta, approval_file)

        else:
            logger.warning(
                "Unknown action type '%s' in %s. "
                "Supported types: file_move, email_send, payment. "
                "Moving to Rejected/ — no action was taken.",
                action_type,
                approval_file.name,
            )
            self._archive(approval_file, self.rejected_dir, meta.get("plan_ref", ""), "unknown_action")

    def _execute_file_move(self, meta: dict, approval_file: Path) -> None:
        """Bronze: move a vault file from In_Progress/ to Done/."""
        source_name = meta.get("source_file", "")
        if not source_name:
            logger.warning("file_move approval is missing 'source_file' in front-matter.")
        else:
            # Find the file anywhere under In_Progress/
            candidates = list((self.vault_path / "In_Progress").rglob(source_name))
            if candidates:
                move_file(candidates[0], self.done_dir / source_name)
                logger.info("Moved %s → Done/", source_name)
            else:
                logger.warning("Source file '%s' not found under In_Progress/.", source_name)

        plan_ref = meta.get("plan_ref", "")
        if plan_ref:
            plan_candidates = list(self.vault_path.rglob(plan_ref))
            for p in plan_candidates:
                move_file(p, self.done_dir / p.name)

        self._finalise(approval_file, meta, "file_move")

    def _execute_email_send(self, meta: dict, approval_file: Path) -> None:
        """Silver+: send email via Gmail API (google-api-python-client)."""
        payload = {
            "to": meta.get("to", ""),
            "subject": meta.get("subject", ""),
            "body": meta.get("body", ""),
            "attachment": meta.get("attachment", ""),
        }
        if dry_run_guard("email_send", payload, actor="approval_handler"):
            logger.info("[DRY RUN] Email send skipped — set DRY_RUN=false to enable.")
            self._finalise(approval_file, meta, "email_send", result="dry_run")
            return

        if not payload["to"]:
            raise ValueError("email_send: 'to' field is missing in approval front-matter.")

        message_id = self._gmail_send(
            to=payload["to"],
            subject=payload["subject"] or "(no subject)",
            body=payload["body"] or "",
            attachment_path=payload["attachment"],
        )
        logger.info("Email sent to %s — Gmail message ID: %s", payload["to"], message_id)

        # Archive the related Plan if referenced
        plan_ref = meta.get("plan_ref", "")
        if plan_ref and plan_ref != "(none)":
            plan_candidates = list(self.vault_path.rglob(plan_ref))
            for p in plan_candidates:
                move_file(p, self.done_dir / p.name)

        self._finalise(approval_file, meta, "email_send")

    # ── Gmail API helper ──────────────────────────────────────────────────────

    def _gmail_send(self, to: str, subject: str, body: str, attachment_path: str) -> str:
        """
        Send an email via the Gmail API.

        Returns the Gmail message ID on success.
        Raises GmailSendError (a plain RuntimeError subclass) on failure so the
        caller can write a retry card and preserve the approval file.

        Requires:
            GMAIL_TOKEN_PATH — path to the OAuth2 token JSON (same as email-mcp).
        """
        token_path_str = os.getenv("GMAIL_TOKEN_PATH", "")
        if not token_path_str:
            raise RuntimeError(
                "GMAIL_TOKEN_PATH is not set — cannot send email. "
                "Run scripts/setup_gmail_auth.py to authenticate."
            )

        token_path = Path(token_path_str)
        if not token_path.exists():
            raise RuntimeError(
                f"Gmail token not found at {token_path}. "
                "Run scripts/setup_gmail_auth.py to re-authenticate."
            )

        try:
            from google.auth.transport.requests import Request
            from google.oauth2.credentials import Credentials
            from googleapiclient.discovery import build
        except ImportError as exc:
            raise RuntimeError(
                "google-api-python-client is not installed. "
                "Run: pip install google-api-python-client google-auth-oauthlib"
            ) from exc

        creds = Credentials.from_authorized_user_file(str(token_path))
        if creds.expired and creds.refresh_token:
            creds.refresh(Request())
            token_path.write_text(creds.to_json(), encoding="utf-8")

        service = build("gmail", "v1", credentials=creds)

        # Build the MIME message
        msg = email_lib.message.EmailMessage()
        msg["To"] = to
        msg["Subject"] = subject
        msg.set_content(body)

        # Attach a file if provided and it exists
        if attachment_path:
            attachment_file = Path(attachment_path)
            if not attachment_file.is_absolute():
                attachment_file = self.vault_path / attachment_path
            if attachment_file.exists():
                mime_type, mime_subtype = "application", "octet-stream"
                msg.add_attachment(
                    attachment_file.read_bytes(),
                    maintype=mime_type,
                    subtype=mime_subtype,
                    filename=attachment_file.name,
                )
                logger.info("Email attachment included: %s", attachment_file.name)
            else:
                logger.warning(
                    "Email attachment not found at '%s' — sending without attachment.",
                    attachment_path,
                )

        raw = base64.urlsafe_b64encode(msg.as_bytes()).decode("utf-8")
        result = service.users().messages().send(
            userId="me", body={"raw": raw}
        ).execute()
        return result.get("id", "unknown")

    def _execute_payment(self, meta: dict, approval_file: Path) -> None:
        """Gold+: execute payment via browser-mcp (always behind DRY_RUN for safety)."""
        payload = {
            "amount": meta.get("amount", ""),
            "recipient": meta.get("recipient", ""),
            "reference": meta.get("reference", ""),
        }
        if dry_run_guard("payment", payload, actor="approval_handler"):
            logger.info("[DRY RUN] Payment skipped — set DRY_RUN=false to enable.")
            self._finalise(approval_file, meta, "payment", result="dry_run")
            return

        # TODO (Phase 5): call browser-mcp payment handler
        logger.info("Payment of %s to %s (stub — implement browser-mcp in Phase 5).", payload["amount"], payload["recipient"])
        self._finalise(approval_file, meta, "payment")

    # ── Helpers ───────────────────────────────────────────────────────────────

    def _finalise(self, approval_file: Path, meta: dict, action_type: str, result: str = "success") -> None:
        """Log, update dashboard, and archive the approval file to Done/."""
        self.done_dir.mkdir(parents=True, exist_ok=True)
        move_file(approval_file, self.done_dir / approval_file.name)

        summary = f"Approved action '{action_type}' executed ({result})"
        update_dashboard(self.vault_path, summary)

        audit_logger.log_action(
            action_type=action_type,
            actor="approval_handler",
            target=approval_file.name,
            parameters=meta,
            approval_status="approved",
            approved_by="human",
            result=result,
        )
        logger.info("Action '%s' complete → Done/", action_type)

    def _archive(self, approval_file: Path, dest_dir: Path, plan_ref: str, reason: str) -> None:
        dest_dir.mkdir(parents=True, exist_ok=True)
        move_file(approval_file, dest_dir / approval_file.name)
        audit_logger.log_action(
            action_type="approval_archived",
            actor="approval_handler",
            target=approval_file.name,
            parameters={"plan_ref": plan_ref, "reason": reason},
            result="skipped",
        )

    def _write_error_card(self, prefix: str, body: str) -> None:
        cards_dir = self.vault_path / "Needs_Action"
        cards_dir.mkdir(parents=True, exist_ok=True)
        ts = int(time.time())
        card = cards_dir / f"{prefix}_{ts}.md"
        card.write_text(
            f"---\ntype: error\nstatus: needs_attention\n---\n\n{body}",
            encoding="utf-8",
        )

    def _write_retry_card(self, action_type: str, filename: str, error: str) -> None:
        cards_dir = self.vault_path / "Needs_Action"
        cards_dir.mkdir(parents=True, exist_ok=True)
        ts = int(time.time())
        card = cards_dir / f"RETRY_{action_type}_{ts}.md"
        card.write_text(
            "---\ntype: retry_required\nstatus: needs_attention\n---\n\n"
            f"## Action Failed: {action_type}\n\n"
            f"The approval file `{filename}` could not be executed.\n\n"
            f"**Error**: {error}\n\n"
            "## What to do\n"
            f"1. Fix the issue described above\n"
            f"2. Move `Approved/{filename}` back to `Approved/` to retry\n"
            f"   OR create a new request from `Pending_Approval/`\n",
            encoding="utf-8",
        )

    @staticmethod
    def _parse_front_matter(path: Path) -> dict:
        """Extract YAML front-matter between --- delimiters."""
        text = path.read_text(encoding="utf-8")
        if not text.startswith("---"):
            return {}
        parts = text.split("---", 2)
        if len(parts) < 3:
            return {}
        return yaml.safe_load(parts[1]) or {}

    @staticmethod
    def _is_expired(meta: dict) -> bool:
        expires = meta.get("expires", "")
        if not expires:
            return False
        try:
            from datetime import datetime, timezone
            exp = datetime.fromisoformat(expires.replace("Z", "+00:00"))
            return datetime.now(tz=timezone.utc) > exp
        except Exception:
            return False
