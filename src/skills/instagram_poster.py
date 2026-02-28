"""
src/skills/instagram_poster.py — Instagram post skill for Digital FTE Agent.

Posts content to an Instagram Business account via the two-step Graph API:
  1. Create a media container  POST /v19.0/{IG_USER_ID}/media
  2. Publish the container     POST /v19.0/{IG_USER_ID}/media_publish

For text-only posts (caption without image), image_url is optional but note
that the Instagram API requires an image or video for most post types.
Pass a publicly accessible image URL for full functionality.

Human-in-the-Loop:
  - AGENT_MODE=cloud  → write Pending_Approval card instead of posting
  - DRY_RUN=true      → log intent, skip API calls

Required environment variables:
  INSTAGRAM_USER_ID     - Instagram Business / Creator account user ID
  INSTAGRAM_ACCESS_TOKEN - Long-lived User or Page access token

Usage:
    from src.skills.instagram_poster import post_instagram_update
    result = post_instagram_update("Caption text", image_url="https://…", vault_path=vault)
"""

import logging
import os
from datetime import datetime, timezone
from pathlib import Path

import httpx

from src.audit import audit_logger
from src.dry_run import dry_run_guard
from src.skills.facebook_poster import _queue_approval_card

logger = logging.getLogger(__name__)

GRAPH_API_BASE = "https://graph.facebook.com/v19.0"
AGENT_MODE = os.getenv("AGENT_MODE", "local")


def post_instagram_update(
    content: str,
    image_url: str | None = None,
    vault_path: Path | None = None,
) -> dict:
    """
    Post a caption (and optional image) to Instagram.

    Args:
        content:    Caption text.
        image_url:  Public URL of the image to attach (required by many post types).
        vault_path: Vault root for DRY_RUN / approval cards.

    Returns:
        dict with keys: media_id (str|None), dry_run (bool), approval_file (str|None)
    """
    if vault_path is None:
        vault_path = Path(os.getenv("VAULT_PATH", "."))

    # ── Cloud agent: queue for local approval ────────────────────────────────
    if AGENT_MODE == "cloud":
        return _queue_approval_card(content, vault_path, platform="instagram")

    # ── DRY_RUN guard ────────────────────────────────────────────────────────
    if dry_run_guard(
        "instagram_post",
        {"content_length": len(content), "has_image": bool(image_url)},
        actor="instagram_poster",
    ):
        logger.info("[DRY RUN] Would post to Instagram (%d chars, image=%s)", len(content), bool(image_url))
        return {"media_id": None, "dry_run": True, "approval_file": None}

    ig_user_id = os.getenv("INSTAGRAM_USER_ID", "")
    access_token = os.getenv("INSTAGRAM_ACCESS_TOKEN", "")

    if not ig_user_id or not access_token:
        logger.error("INSTAGRAM_USER_ID or INSTAGRAM_ACCESS_TOKEN not set.")
        return {"media_id": None, "dry_run": False, "error": "credentials_missing"}

    try:
        # Step 1: Create media container
        container_id = _create_media_container(ig_user_id, access_token, content, image_url)

        # Step 2: Publish container
        media_id = _publish_media_container(ig_user_id, access_token, container_id)

        audit_logger.log_action(
            action_type="instagram_post",
            actor="instagram_poster",
            target=f"user:{ig_user_id}",
            parameters={"content_length": len(content), "has_image": bool(image_url)},
            result=f"media_id:{media_id}",
        )
        logger.info("Instagram post published — media_id: %s", media_id)
        return {"media_id": media_id, "dry_run": False, "approval_file": None}

    except httpx.HTTPStatusError as exc:
        logger.error("Instagram API error %s: %s", exc.response.status_code, exc.response.text)
        raise
    except Exception as exc:
        logger.error("Instagram post failed: %s", exc)
        raise


def _create_media_container(
    ig_user_id: str,
    access_token: str,
    caption: str,
    image_url: str | None,
) -> str:
    """Step 1: Create an Instagram media container. Returns container_id."""
    url = f"{GRAPH_API_BASE}/{ig_user_id}/media"
    payload: dict = {"caption": caption, "access_token": access_token}
    if image_url:
        payload["image_url"] = image_url
        payload["media_type"] = "IMAGE"

    response = httpx.post(url, data=payload, timeout=30)
    response.raise_for_status()
    container_id = response.json().get("id")
    if not container_id:
        raise ValueError(f"No container_id in response: {response.text}")
    logger.debug("Instagram container created: %s", container_id)
    return container_id


def _publish_media_container(ig_user_id: str, access_token: str, container_id: str) -> str:
    """Step 2: Publish a media container. Returns media_id."""
    url = f"{GRAPH_API_BASE}/{ig_user_id}/media_publish"
    payload = {"creation_id": container_id, "access_token": access_token}

    response = httpx.post(url, data=payload, timeout=30)
    response.raise_for_status()
    media_id = response.json().get("id")
    if not media_id:
        raise ValueError(f"No media_id in publish response: {response.text}")
    logger.debug("Instagram media published: %s", media_id)
    return media_id
