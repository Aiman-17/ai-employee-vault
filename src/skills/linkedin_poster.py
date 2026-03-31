"""
src/skills/linkedin_poster.py — LinkedIn post publisher (Silver tier).

Posts content to LinkedIn via the LinkedIn API (v2).
Always respects DRY_RUN and AGENT_MODE — cloud agents may draft posts
but not publish without Local approval.

Environment variables:
    LINKEDIN_ACCESS_TOKEN   OAuth2 access token from LinkedIn Developer Portal.
    LINKEDIN_AUTHOR_URN     LinkedIn Person URN (format: urn:li:person:<id>).
    DRY_RUN                 Set to 'false' to enable real posting (default: true).
    AGENT_MODE              'cloud' blocks direct posting; creates approval file instead.

Usage (called from an Agent Skill or directly):
    from src.skills.linkedin_poster import post_linkedin_update

    result = post_linkedin_update(
        content="Excited to announce our new AI Employee project!",
        visibility="PUBLIC",
    )

Getting your credentials:
    1. Go to https://www.linkedin.com/developers/ → Create an app.
    2. Request the 'Share on LinkedIn' (w_member_social) permission.
    3. Complete OAuth2 flow to get your access token.
    4. Find your Person URN at: https://api.linkedin.com/v2/me
    5. Add LINKEDIN_ACCESS_TOKEN and LINKEDIN_AUTHOR_URN to .env.
"""

import json
import logging
import os
import time
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)

LINKEDIN_API_BASE = "https://api.linkedin.com/v2"
DRY_RUN = os.getenv("DRY_RUN", "true").lower() != "false"
AGENT_MODE = os.getenv("AGENT_MODE", "local")


# ── Public API ────────────────────────────────────────────────────────────────

def post_linkedin_update(
    content: str,
    visibility: str = "PUBLIC",
    vault_path: Path | None = None,
) -> dict:
    """
    Post a text update to LinkedIn.

    Args:
        content    : The text to post (max 3000 characters recommended).
        visibility : 'PUBLIC' (default) or 'CONNECTIONS'.
        vault_path : Vault root for writing approval files (uses VAULT_PATH env if None).

    Returns:
        dict with keys: success (bool), post_id (str), message (str).

    Raises:
        LinkedInError: if the API call fails after retries.
    """
    if len(content) > 3000:
        logger.warning("LinkedIn post content is %d characters — truncating to 3000.", len(content))
        content = content[:2997] + "…"

    # Cloud agents: write approval file and return — never post directly
    if AGENT_MODE == "cloud":
        return _write_cloud_approval(content, visibility, vault_path)

    if DRY_RUN:
        logger.info("[DRY RUN] Would post to LinkedIn: %s…", content[:80])
        return {
            "success": True,
            "dry_run": True,
            "post_id": "dry-run-post",
            "message": f"[DRY RUN] LinkedIn post simulated — {len(content)} characters.",
        }

    token = _require_env("LINKEDIN_ACCESS_TOKEN")
    author_urn = _require_env("LINKEDIN_AUTHOR_URN")

    payload = _build_share_payload(content, author_urn, visibility)
    return _send_post_request(payload, token)


def draft_linkedin_post(
    content: str,
    topic: str = "business update",
    vault_path: Path | None = None,
) -> Path:
    """
    Write a draft LinkedIn post to Pending_Approval/ without publishing.
    Returns the path to the approval file.
    Always safe — never calls the API.
    """
    if vault_path is None:
        vault_env = os.getenv("VAULT_PATH", "")
        vault_path = Path(vault_env) if vault_env else Path(".")

    return _write_cloud_approval(content, "PUBLIC", vault_path, topic=topic)


# ── Internal helpers ──────────────────────────────────────────────────────────

def _build_share_payload(content: str, author_urn: str, visibility: str) -> dict:
    """Build the LinkedIn UGC Post payload."""
    return {
        "author": author_urn,
        "lifecycleState": "PUBLISHED",
        "specificContent": {
            "com.linkedin.ugc.ShareContent": {
                "shareCommentary": {
                    "text": content
                },
                "shareMediaCategory": "NONE"
            }
        },
        "visibility": {
            "com.linkedin.ugc.MemberNetworkVisibility": visibility
        }
    }


def _send_post_request(payload: dict, token: str) -> dict:
    """Send the post to LinkedIn API with retry on rate limit."""
    try:
        import httpx
    except ImportError as exc:
        raise LinkedInError(
            "httpx is not installed. Run: pip install httpx"
        ) from exc

    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
        "X-Restli-Protocol-Version": "2.0.0",
    }
    url = f"{LINKEDIN_API_BASE}/ugcPosts"

    for attempt in range(3):
        try:
            response = httpx.post(url, headers=headers, json=payload, timeout=30)

            if response.status_code == 201:
                post_id = response.headers.get("x-restli-id", "unknown")
                logger.info("LinkedIn post published — post_id: %s", post_id)
                return {
                    "success": True,
                    "post_id": post_id,
                    "message": "Post published successfully.",
                }

            if response.status_code == 429:
                retry_after = int(response.headers.get("Retry-After", "60"))
                logger.warning(
                    "LinkedIn rate limit — waiting %ds (attempt %d/3)", retry_after, attempt + 1
                )
                time.sleep(retry_after)
                continue

            if response.status_code in (401, 403):
                raise LinkedInError(
                    f"LinkedIn API auth failure ({response.status_code}): {response.text}\n"
                    "Check LINKEDIN_ACCESS_TOKEN — it may have expired. "
                    "Re-authorise at https://www.linkedin.com/developers/"
                )

            raise LinkedInError(
                f"LinkedIn API error {response.status_code}: {response.text}"
            )

        except (LinkedInError, ImportError):
            raise
        except Exception as exc:
            if attempt == 2:
                raise LinkedInError(f"Network error after 3 attempts: {exc}") from exc
            logger.warning("LinkedIn request failed (attempt %d/3): %s — retrying", attempt + 1, exc)
            time.sleep(2 ** attempt)

    raise LinkedInError("LinkedIn post failed after 3 attempts.")


def _write_cloud_approval(
    content: str,
    visibility: str,
    vault_path: Path | None,
    topic: str = "linkedin post",
) -> dict:
    """Write a Pending_Approval/ file for a LinkedIn post. Returns status dict."""
    if vault_path is None:
        vault_env = os.getenv("VAULT_PATH", "")
        vault_path = Path(vault_env) if vault_env else Path(".")

    approval_dir = vault_path / "Pending_Approval"
    approval_dir.mkdir(parents=True, exist_ok=True)

    ts = int(time.time())
    created = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    expires = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(ts + 48 * 3600))

    approval_file = approval_dir / f"LINKEDIN_post_{ts}.md"
    approval_file.write_text(
        "\n".join([
            "---",
            "type: approval_request",
            "action: linkedin_post",
            f"topic: {topic}",
            f"visibility: {visibility}",
            f"created: {created}",
            f"expires: {expires}",
            "status: pending",
            "---",
            "",
            "## LinkedIn Post Draft",
            "",
            "Review the post below. Move this file to `/Approved` to publish",
            "or `/Rejected` to discard.",
            "",
            "---",
            "",
            content,
            "",
            "---",
            "",
            f"*Drafted by Digital FTE Agent — visibility: {visibility}*",
        ]),
        encoding="utf-8",
    )
    logger.info("LinkedIn approval file written: %s", approval_file.name)
    return {
        "success": True,
        "approval_file": str(approval_file),
        "message": f"LinkedIn post draft saved — approve at Pending_Approval/{approval_file.name}",
    }


def _require_env(var: str) -> str:
    """Return env var value or raise LinkedInError with a clear message."""
    value = os.getenv(var, "")
    if not value:
        raise LinkedInError(
            f"{var} is not set.\n"
            "Add it to .env:\n"
            f"  {var}=your_value_here\n"
            "See src/skills/linkedin_poster.py docstring for setup instructions."
        )
    return value


# ── Custom exception ──────────────────────────────────────────────────────────

class LinkedInError(Exception):
    """Raised when a LinkedIn API call fails."""
