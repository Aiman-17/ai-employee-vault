"""
src/mcp_servers/odoo_mcp/server.py — Odoo MCP Server for Digital FTE Agent.

Exposes three MCP tools via FastMCP (stdio transport):
  - odoo_search_read : Query records from any Odoo model
  - odoo_create_draft: Create a draft record (DRY_RUN guarded)
  - odoo_post_record : Post/validate a draft record (HITL approval-token gate)

Authentication uses Odoo's XML-RPC endpoint (/xmlrpc/2/common and /xmlrpc/2/object).
For Odoo 19+, the same credentials work; swap to JSON-RPC if preferred.

Configure via .env:
  ODOO_URL       = http://localhost:8069
  ODOO_DB        = my_database
  ODOO_USERNAME  = admin
  ODOO_PASSWORD  = admin
  VAULT_PATH     = /path/to/vault

Run standalone:
  uv run python -m src.mcp_servers.odoo_mcp.server
"""

import logging
import os
import xmlrpc.client
from datetime import date
from pathlib import Path
from typing import Any

from dotenv import load_dotenv
from mcp.server.fastmcp import FastMCP

from src.audit import audit_logger
from src.dry_run import dry_run_guard

load_dotenv()

logger = logging.getLogger(__name__)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [odoo_mcp] %(levelname)s: %(message)s",
)

ODOO_URL = os.getenv("ODOO_URL", "http://localhost:8069")
ODOO_DB = os.getenv("ODOO_DB", "")
ODOO_USERNAME = os.getenv("ODOO_USERNAME", "admin")
ODOO_PASSWORD = os.getenv("ODOO_PASSWORD", "")
VAULT_PATH = Path(os.getenv("VAULT_PATH", "."))

mcp = FastMCP("odoo")

# ── Odoo XML-RPC helpers ──────────────────────────────────────────────────────

_cached_uid: int | None = None


def _odoo_uid() -> int:
    """Authenticate with Odoo and return uid (cached per process invocation)."""
    global _cached_uid
    if _cached_uid is not None:
        return _cached_uid
    if not ODOO_DB or not ODOO_PASSWORD:
        raise RuntimeError(
            "ODOO_DB and ODOO_PASSWORD must be set in .env to use the Odoo MCP server."
        )
    common = xmlrpc.client.ServerProxy(f"{ODOO_URL}/xmlrpc/2/common")
    uid = common.authenticate(ODOO_DB, ODOO_USERNAME, ODOO_PASSWORD, {})
    if not uid:
        raise RuntimeError(
            "Odoo authentication failed — check ODOO_URL, ODOO_DB, ODOO_USERNAME, ODOO_PASSWORD."
        )
    _cached_uid = uid
    return uid


def _odoo_execute(model: str, method: str, *args: Any, **kwargs: Any) -> Any:
    """Execute a single Odoo XML-RPC object call."""
    uid = _odoo_uid()
    models = xmlrpc.client.ServerProxy(f"{ODOO_URL}/xmlrpc/2/object")
    return models.execute_kw(ODOO_DB, uid, ODOO_PASSWORD, model, method, list(args), kwargs)


# ── MCP Tools ────────────────────────────────────────────────────────────────


@mcp.tool()
def odoo_search_read(
    model: str,
    domain: list,
    fields: list[str],
    limit: int = 100,
) -> list[dict]:
    """
    Search and read records from an Odoo model.

    Args:
        model:  Odoo model name, e.g. "account.move", "sale.order", "res.partner".
        domain: Odoo domain filter list, e.g. [["state","=","draft"]].
                Pass [] to return all records (up to limit).
        fields: Field names to include in each result, e.g. ["name","amount_total"].
        limit:  Maximum number of records to return (default 100).

    Returns:
        List of record dicts, each containing the requested fields plus "id".

    Example:
        odoo_search_read("account.move", [["state","=","draft"]], ["name","amount_total"])
    """
    try:
        records = _odoo_execute(
            model, "search_read", domain, fields=fields, limit=limit
        )
        audit_logger.log_action(
            action_type="odoo_search_read",
            actor="odoo_mcp",
            target=model,
            parameters={"domain": domain, "fields": fields, "limit": limit},
            result=f"{len(records)} records returned",
        )
        logger.info("odoo_search_read %s → %d records", model, len(records))
        return records
    except Exception as exc:
        logger.error("odoo_search_read failed for %s: %s", model, exc)
        raise


@mcp.tool()
def odoo_create_draft(model: str, vals: dict) -> dict:
    """
    Create a new draft record in Odoo (DRY_RUN guarded).

    In DRY_RUN mode (DRY_RUN=true) no record is created; returns dry_run=True.

    Args:
        model: Odoo model name, e.g. "account.move".
        vals:  Field values for the new record, e.g. {"partner_id": 5, "move_type": "out_invoice"}.

    Returns:
        {"record_id": int | None, "dry_run": bool}

    Example:
        odoo_create_draft("account.move", {"partner_id": 5, "move_type": "out_invoice"})
    """
    if dry_run_guard("odoo_create_draft", {"model": model, "vals": vals}, actor="odoo_mcp"):
        logger.info("[DRY RUN] Would create %s with vals: %s", model, vals)
        return {"record_id": None, "dry_run": True}

    try:
        record_id = _odoo_execute(model, "create", vals)
        audit_logger.log_action(
            action_type="odoo_create_draft",
            actor="odoo_mcp",
            target=f"{model}:{record_id}",
            parameters={"vals": vals},
            result="created",
        )
        logger.info("odoo_create_draft %s → record_id=%d", model, record_id)
        return {"record_id": record_id, "dry_run": False}
    except Exception as exc:
        logger.error("odoo_create_draft failed for %s: %s", model, exc)
        raise


@mcp.tool()
def odoo_post_record(model: str, record_id: int, approval_token: str) -> dict:
    """
    Post (confirm / validate) a draft Odoo record after human approval.

    This tool is gated behind a file-based HITL approval mechanism:
      1. Caller provides an approval_token (e.g. "ODOO_invoice_2026-01-07").
      2. If VAULT_PATH/Approved/<token>.md exists → proceed with posting.
      3. If not → create VAULT_PATH/Pending_Approval/<token>.md and return posted=False.

    The human reviews the Pending_Approval card, then moves it to Approved/ to unblock.

    Args:
        model:          Odoo model, e.g. "account.move".
        record_id:      Integer ID of the draft record to post.
        approval_token: Filename stem (no extension) of the approval card.

    Returns:
        {"posted": bool, "approval_checked": str, "dry_run": bool}

    Example:
        odoo_post_record("account.move", 42, "ODOO_invoice_client_a_2026-01-07")
    """
    approval_file = VAULT_PATH / "Approved" / f"{approval_token}.md"

    if not approval_file.exists():
        # Create (idempotent) pending approval card
        pending = VAULT_PATH / "Pending_Approval" / f"{approval_token}.md"
        pending.parent.mkdir(parents=True, exist_ok=True)

        if not pending.exists():
            today_str = date.today().isoformat()
            pending.write_text(
                f"---\n"
                f"type: odoo_post_approval\n"
                f"model: {model}\n"
                f"record_id: {record_id}\n"
                f"token: {approval_token}\n"
                f"status: pending\n"
                f"created: {today_str}\n"
                f"---\n\n"
                f"## Odoo Record Posting Approval\n\n"
                f"Your Digital FTE wants to **post** (confirm/validate) the following Odoo record:\n\n"
                f"| Field | Value |\n"
                f"|-------|-------|\n"
                f"| Model | `{model}` |\n"
                f"| Record ID | `{record_id}` |\n\n"
                f"## To Approve\n"
                f"Move this file to `/Approved` to proceed.\n\n"
                f"## To Reject\n"
                f"Move this file to `/Rejected` to cancel.\n",
                encoding="utf-8",
            )
            logger.info("Pending approval card created: %s", pending.name)

        return {"posted": False, "approval_checked": str(pending), "dry_run": False}

    # Approval exists — proceed
    if dry_run_guard("odoo_post_record", {"model": model, "record_id": record_id}, actor="odoo_mcp"):
        logger.info("[DRY RUN] Would post %s record %d", model, record_id)
        return {"posted": False, "approval_checked": str(approval_file), "dry_run": True}

    try:
        # action_post is the standard Odoo method for confirming invoices/orders
        _odoo_execute(model, "action_post", [record_id])
        audit_logger.log_action(
            action_type="odoo_post_record",
            actor="odoo_mcp",
            target=f"{model}:{record_id}",
            parameters={"approval_token": approval_token},
            result="posted",
        )
        logger.info("Odoo record posted: %s:%d", model, record_id)
        return {"posted": True, "approval_checked": str(approval_file), "dry_run": False}
    except Exception as exc:
        logger.error("odoo_post_record failed for %s:%d — %s", model, record_id, exc)
        raise


# ── Entry point ───────────────────────────────────────────────────────────────

if __name__ == "__main__":
    mcp.run(transport="stdio")
