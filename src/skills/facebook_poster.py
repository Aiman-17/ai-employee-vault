"""
src/skills/facebook_poster.py — Facebook Page post skill for Digital FTE Agent.

Posts text content to a Facebook Page via the Graph API v19.0.

Human-in-the-Loop:
  - AGENT_MODE=cloud  → write Pending_Approval card instead of posting
  - DRY_RUN=true      → log intent, skip API call

Required environment variables:
  FACEBOOK_PAGE_ID      - The numeric Facebook Page ID
  FACEBOOK_ACCESS_TOKEN - Long-lived Page access token

Usage:
    from src.skills.facebook_poster import post_facebook_update
    result = post_facebook_update("Weekly update text…", vault_path=vault)
"""

import logging
import os
import re
from datetime import datetime, timezone
from pathlib import Path

import httpx

from src.audit import audit_logger
from src.dry_run import dry_run_guard

logger = logging.getLogger(__name__)

GRAPH_API_BASE = "https://graph.facebook.com/v19.0"
AGENT_MODE = os.getenv("AGENT_MODE", "local")


def post_facebook_update(content: str, vault_path: Path | None = None) -> dict:
    """
    Post a text update to the configured Facebook Page.

    Args:
        content:    Text to post (max ~63,206 chars per Facebook limits).
        vault_path: Vault root — used for DRY_RUN / approval card writing.

    Returns:
        dict with keys: post_id (str|None), dry_run (bool), approval_file (str|None)
    """
    if vault_path is None:
        vault_path = Path(os.getenv("VAULT_PATH", "."))

    # ── Cloud agent: queue for local approval ────────────────────────────────
    if AGENT_MODE == "cloud":
        return _queue_approval_card(content, vault_path, platform="facebook")

    # ── DRY_RUN guard ────────────────────────────────────────────────────────
    if dry_run_guard("facebook_post", {"content_length": len(content)}, actor="facebook_poster"):
        logger.info("[DRY RUN] Would post to Facebook (%d chars)", len(content))
        return {"post_id": None, "dry_run": True, "approval_file": None}

    page_id = os.getenv("FACEBOOK_PAGE_ID", "")
    access_token = os.getenv("FACEBOOK_ACCESS_TOKEN", "")

    if not page_id or not access_token:
        logger.error(
            "FACEBOOK_PAGE_ID or FACEBOOK_ACCESS_TOKEN not set — cannot post."
        )
        return {"post_id": None, "dry_run": False, "error": "credentials_missing"}

    url = f"{GRAPH_API_BASE}/{page_id}/feed"
    payload = {"message": content, "access_token": access_token}

    try:
        response = httpx.post(url, data=payload, timeout=30)
        response.raise_for_status()
        post_id = response.json().get("id", "unknown")

        audit_logger.log_action(
            action_type="facebook_post",
            actor="facebook_poster",
            target=f"page:{page_id}",
            parameters={"content_length": len(content)},
            result=f"post_id:{post_id}",
        )
        logger.info("Facebook post published — post_id: %s", post_id)
        return {"post_id": post_id, "dry_run": False, "approval_file": None}

    except httpx.HTTPStatusError as exc:
        logger.error("Facebook API error %s: %s", exc.response.status_code, exc.response.text)
        raise
    except Exception as exc:
        logger.error("Facebook post failed: %s", exc)
        raise


def _queue_approval_card(content: str, vault_path: Path, platform: str) -> dict:
    """Write a Pending_Approval card for cloud-queued social posts."""
    approval_dir = vault_path / "Pending_Approval"
    approval_dir.mkdir(parents=True, exist_ok=True)

    slug = re.sub(r"[^a-z0-9]+", "_", content[:40].lower()).strip("_")
    today_str = datetime.now(tz=timezone.utc).strftime("%Y-%m-%d")
    card_path = approval_dir / f"SOCIAL_{platform.upper()}_{slug}_{today_str}.md"

    card_path.write_text(
        f"---\n"
        f"type: social_post_approval\n"
        f"platform: {platform}\n"
        f"status: pending\n"
        f"created: {datetime.now(tz=timezone.utc).isoformat()}\n"
        f"---\n\n"
        f"## Social Post Approval: {platform.capitalize()}\n\n"
        f"**Content preview:**\n\n> {content[:200]}{'…' if len(content) > 200 else ''}\n\n"
        f"## To Approve\n"
        f"Move this file to `/Approved` to publish the post.\n\n"
        f"## To Reject\n"
        f"Move this file to `/Rejected` to discard.\n",
        encoding="utf-8",
    )
    logger.info("Cloud agent: social approval card created — %s", card_path.name)
    return {"post_id": None, "dry_run": False, "approval_file": str(card_path)}
