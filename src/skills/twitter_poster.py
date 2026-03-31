"""
src/skills/twitter_poster.py — Twitter/X post skill for Digital FTE Agent.

Posts text content to Twitter/X via the Tweepy v4 client (API v2).
Rate-limit state is persisted in VAULT_PATH/State/twitter_state.json to
prevent 429 errors across process restarts.

Twitter API v2 free tier limits (as of 2026):
  - 17 posts per 24 hours for app-level write access

Human-in-the-Loop:
  - AGENT_MODE=cloud  → write Pending_Approval card instead of posting
  - DRY_RUN=true      → log intent, skip API call

Required environment variables:
  TWITTER_BEARER_TOKEN          - OAuth 2.0 app bearer token
  TWITTER_API_KEY               - OAuth 1.0a consumer key
  TWITTER_API_SECRET            - OAuth 1.0a consumer secret
  TWITTER_ACCESS_TOKEN          - OAuth 1.0a access token
  TWITTER_ACCESS_TOKEN_SECRET   - OAuth 1.0a access token secret

Usage:
    from src.skills.twitter_poster import post_twitter_update
    result = post_twitter_update("Tweet text (≤280 chars)", vault_path=vault)
"""

import json
import logging
import os
from datetime import datetime, timezone
from pathlib import Path

from src.audit import audit_logger
from src.dry_run import dry_run_guard
from src.skills.facebook_poster import _queue_approval_card

logger = logging.getLogger(__name__)

AGENT_MODE = os.getenv("AGENT_MODE", "local")
TWITTER_MAX_CHARS = 280
DAILY_POST_LIMIT = int(os.getenv("TWITTER_DAILY_LIMIT", "17"))  # free tier default


def post_twitter_update(content: str, vault_path: Path | None = None) -> dict:
    """
    Post a tweet via the Twitter API v2.

    Args:
        content:    Tweet text (will be truncated to 280 chars with ellipsis if longer).
        vault_path: Vault root for rate-limit state and approval cards.

    Returns:
        dict with keys: tweet_id (str|None), dry_run (bool), approval_file (str|None),
                        rate_limited (bool)
    """
    if vault_path is None:
        vault_path = Path(os.getenv("VAULT_PATH", "."))

    # ── Cloud agent: queue for local approval ────────────────────────────────
    if AGENT_MODE == "cloud":
        return _queue_approval_card(content, vault_path, platform="twitter")

    # ── Truncate to Twitter limit ─────────────────────────────────────────────
    if len(content) > TWITTER_MAX_CHARS:
        content = content[: TWITTER_MAX_CHARS - 1] + "…"

    # ── DRY_RUN guard ────────────────────────────────────────────────────────
    if dry_run_guard("twitter_post", {"content_length": len(content)}, actor="twitter_poster"):
        logger.info("[DRY RUN] Would tweet (%d chars)", len(content))
        return {"tweet_id": None, "dry_run": True, "rate_limited": False, "approval_file": None}

    # ── Rate-limit check ─────────────────────────────────────────────────────
    state = _load_twitter_state(vault_path)
    if _is_rate_limited(state):
        logger.warning(
            "Twitter daily post limit reached (%d/%d). Skipping post.",
            state.get("posts_today", 0),
            DAILY_POST_LIMIT,
        )
        return {"tweet_id": None, "dry_run": False, "rate_limited": True, "approval_file": None}

    # ── Resolve credentials (accept both naming conventions) ─────────────────
    def _get_twitter_env(primary: str, fallback: str) -> str | None:
        return os.getenv(primary) or os.getenv(fallback)

    api_key    = _get_twitter_env("TWITTER_API_KEY",    "TWITTER_CONSUMER_KEY")
    api_secret = _get_twitter_env("TWITTER_API_SECRET", "TWITTER_CONSUMER_KEY_SECRET")
    acc_token  = os.getenv("TWITTER_ACCESS_TOKEN")
    acc_secret = os.getenv("TWITTER_ACCESS_TOKEN_SECRET")

    missing = [n for n, v in [
        ("TWITTER_API_KEY/CONSUMER_KEY", api_key),
        ("TWITTER_API_SECRET/CONSUMER_KEY_SECRET", api_secret),
        ("TWITTER_ACCESS_TOKEN", acc_token),
        ("TWITTER_ACCESS_TOKEN_SECRET", acc_secret),
    ] if not v]
    if missing:
        logger.error("Missing Twitter credentials: %s", missing)
        return {"tweet_id": None, "dry_run": False, "error": "credentials_missing"}

    # ── Post via tweepy ───────────────────────────────────────────────────────
    try:
        import tweepy  # optional dependency

        client = tweepy.Client(
            bearer_token=os.getenv("TWITTER_BEARER_TOKEN"),
            consumer_key=api_key,
            consumer_secret=api_secret,
            access_token=acc_token,
            access_token_secret=acc_secret,
        )
        response = client.create_tweet(text=content)
        tweet_id = response.data["id"]

        # Update rate-limit state
        _increment_post_count(state, vault_path)

        audit_logger.log_action(
            action_type="twitter_post",
            actor="twitter_poster",
            target="twitter",
            parameters={"content_length": len(content)},
            result=f"tweet_id:{tweet_id}",
        )
        logger.info("Tweet published — tweet_id: %s", tweet_id)
        return {"tweet_id": tweet_id, "dry_run": False, "rate_limited": False, "approval_file": None}

    except ImportError:
        logger.error("tweepy not installed — run: pip install tweepy")
        raise
    except Exception as exc:
        logger.error("Twitter post failed: %s", exc)
        raise


# ── Rate-limit state helpers ──────────────────────────────────────────────────

def _state_path(vault_path: Path) -> Path:
    state_dir = vault_path / "State"
    state_dir.mkdir(parents=True, exist_ok=True)
    return state_dir / "twitter_state.json"


def _load_twitter_state(vault_path: Path) -> dict:
    path = _state_path(vault_path)
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _save_twitter_state(state: dict, vault_path: Path) -> None:
    path = _state_path(vault_path)
    path.write_text(json.dumps(state, indent=2), encoding="utf-8")


def _is_rate_limited(state: dict) -> bool:
    today = datetime.now(tz=timezone.utc).strftime("%Y-%m-%d")
    if state.get("date") != today:
        return False  # new day, counter resets
    return state.get("posts_today", 0) >= DAILY_POST_LIMIT


def _increment_post_count(state: dict, vault_path: Path) -> None:
    today = datetime.now(tz=timezone.utc).strftime("%Y-%m-%d")
    if state.get("date") != today:
        state["date"] = today
        state["posts_today"] = 0
    state["posts_today"] = state.get("posts_today", 0) + 1
    state["last_post"] = datetime.now(tz=timezone.utc).isoformat()
    _save_twitter_state(state, vault_path)
