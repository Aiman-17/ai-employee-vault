"""
src/orchestrator/main.py — Entry point for the local orchestrator.

Registers all active-tier components and starts the Orchestrator.
Each Silver/Gold watcher is registered only when its required env var is set,
so the orchestrator starts cleanly even when only some integrations are configured.

Run directly:  uv run python -m src.orchestrator.main
Via PM2:       pm2 start pm2.config.js
"""

import logging
import os

from dotenv import load_dotenv

from src.orchestrator.approval_handler import ApprovalHandler
from src.orchestrator.orchestrator import Orchestrator
from src.watchers.filesystem_watcher import FilesystemWatcher

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
    handlers=[
        logging.StreamHandler(),
        # PM2 captures stdout — log file path set in pm2.config.js
    ],
)
logger = logging.getLogger(__name__)


def build_orchestrator() -> Orchestrator:
    orc = Orchestrator()

    # ── Bronze: Filesystem Watcher ────────────────────────────────────────────
    orc.register_watcher(FilesystemWatcher(check_interval=5))

    # ── Bronze: Approval Handler (runs in its own thread) ────────────────────
    approval = ApprovalHandler()
    approval.start()

    # ── Silver: GmailWatcher (requires GMAIL_TOKEN_PATH) ─────────────────────
    if os.getenv("GMAIL_TOKEN_PATH"):
        from src.watchers.gmail_watcher import GmailWatcher
        orc.register_watcher(GmailWatcher(check_interval=120))
        logger.info("GmailWatcher registered.")
    else:
        logger.info(
            "GmailWatcher skipped — GMAIL_TOKEN_PATH not set. "
            "Run scripts/setup_gmail_auth.py to enable Gmail monitoring."
        )

    # ── Silver: WhatsAppWatcher (requires WHATSAPP_SESSION_PATH) ─────────────
    if os.getenv("WHATSAPP_SESSION_PATH"):
        from src.watchers.whatsapp_watcher import WhatsAppWatcher
        orc.register_watcher(WhatsAppWatcher(check_interval=30))
        logger.info("WhatsAppWatcher registered.")
    else:
        logger.info(
            "WhatsAppWatcher skipped — WHATSAPP_SESSION_PATH not set. "
            "Set WHATSAPP_SESSION_PATH in .env to enable WhatsApp monitoring."
        )

    # ── Silver: FinanceWatcher (requires BANK_CSV_DROP_PATH) ─────────────────
    if os.getenv("BANK_CSV_DROP_PATH"):
        from src.watchers.finance_watcher import FinanceWatcher
        orc.register_watcher(FinanceWatcher(check_interval=3600))
        logger.info("FinanceWatcher registered.")
    else:
        logger.info(
            "FinanceWatcher skipped — BANK_CSV_DROP_PATH not set. "
            "Set BANK_CSV_DROP_PATH in .env to enable bank CSV monitoring."
        )

    # ── Silver: LinkedIn Weekly Post (requires LINKEDIN_ACCESS_TOKEN) ────────
    if os.getenv("LINKEDIN_ACCESS_TOKEN"):
        from src.skills.linkedin_poster import post_linkedin_update

        def _post_linkedin_weekly() -> None:
            """Post a weekly business highlight to LinkedIn every Monday at 09:00."""
            vault_path = orc.vault_path
            goals_file = vault_path / "Business_Goals.md"
            if goals_file.exists():
                content = goals_file.read_text(encoding="utf-8")[:2000]
                highlight = f"Weekly business update from your Digital FTE:\n\n{content}"
            else:
                highlight = (
                    "Your Digital FTE Agent is running smoothly this week! "
                    "Monitoring emails, WhatsApp messages, and bank transactions — "
                    "keeping your business on autopilot. #AI #Automation #DigitalFTE"
                )
            result = post_linkedin_update(highlight, vault_path=vault_path)
            if result.get("dry_run"):
                logger.info("LinkedIn weekly post — DRY RUN (set DRY_RUN=false to publish).")
            elif result.get("approval_file"):
                logger.info("LinkedIn post queued for approval: %s", result["approval_file"])
            else:
                logger.info("LinkedIn weekly post published — post_id: %s", result.get("post_id"))

        # 7 days in seconds — fires once per week; PM2 restarts ensure timing alignment
        orc.register_schedule(7 * 24 * 3600, _post_linkedin_weekly)
        logger.info("LinkedIn weekly post schedule registered (every 7 days).")
    else:
        logger.info(
            "LinkedIn weekly post skipped — LINKEDIN_ACCESS_TOKEN not set. "
            "Add LINKEDIN_ACCESS_TOKEN and LINKEDIN_AUTHOR_URN to .env to enable."
        )

    # ── Gold: Weekly CEO Briefing (every Sunday night) ────────────────────────
    from src.audit.ceo_briefing import generate_briefing
    from datetime import date, timedelta

    def _weekly_ceo_briefing() -> None:
        """Generate the Monday Morning CEO Briefing for the past 7 days."""
        vault_path = orc.vault_path
        period_end = date.today()
        period_start = period_end - timedelta(days=7)
        try:
            briefing = generate_briefing(vault_path, period_start, period_end)
            logger.info("CEO Briefing generated: %s", briefing.name)
        except Exception as exc:
            logger.error("CEO Briefing generation failed: %s", exc)

    orc.register_schedule(7 * 24 * 3600, _weekly_ceo_briefing)
    logger.info("CEO Briefing schedule registered (every 7 days).")

    # ── Platinum: Cloud Update Merge (Local only) ────────────────────────────
    # Reads pending dashboard update cards from Updates/ and merges them into
    # Dashboard.md.  Runs only when AGENT_MODE=local (default).
    if os.getenv("AGENT_MODE", "local").lower() == "local":
        from src.vault_utils import update_dashboard

        def _merge_cloud_updates() -> None:
            """Merge dashboard_update_*.md cards from Updates/ into Dashboard.md."""
            vault_path = orc.vault_path
            updates_dir = vault_path / "Updates"
            if not updates_dir.exists():
                return
            done_dir = vault_path / "Done" / "Updates"
            done_dir.mkdir(parents=True, exist_ok=True)
            cards = sorted(updates_dir.glob("dashboard_update_*.md"))
            if not cards:
                return
            for card in cards:
                try:
                    text = card.read_text(encoding="utf-8")
                    # Strip YAML front-matter (--- … ---\n\n) and grab the body
                    lines = text.splitlines()
                    body_start = 0
                    if lines and lines[0].strip() == "---":
                        try:
                            end_idx = lines.index("---", 1)
                            body_start = end_idx + 1
                        except ValueError:
                            pass
                    body = "\n".join(lines[body_start:]).strip()
                    if body:
                        update_dashboard(vault_path, body)
                        logger.info("Merged cloud update: %s", card.name)
                    card.rename(done_dir / card.name)
                except Exception as exc:
                    logger.warning("Failed to merge cloud update %s: %s", card.name, exc)

        # Poll every VAULT_SYNC_INTERVAL_MINUTES (default 15 min)
        sync_interval = int(os.getenv("VAULT_SYNC_INTERVAL_MINUTES", "15")) * 60
        orc.register_schedule(sync_interval, _merge_cloud_updates)
        logger.info(
            "Cloud update merge registered (every %s min).",
            os.getenv("VAULT_SYNC_INTERVAL_MINUTES", "15"),
        )

    # ── Gold: Social media weekly post — Monday 09:30 ─────────────────────────
    # Facebook (requires FACEBOOK_PAGE_ID + FACEBOOK_ACCESS_TOKEN)
    if os.getenv("FACEBOOK_PAGE_ID") and os.getenv("FACEBOOK_ACCESS_TOKEN"):
        from src.skills.facebook_poster import post_facebook_update

        def _post_facebook_weekly() -> None:
            """Post a weekly business update to the Facebook Page."""
            vault_path = orc.vault_path
            goals_file = vault_path / "Business_Goals.md"
            content = (
                goals_file.read_text(encoding="utf-8")[:1800]
                if goals_file.exists()
                else (
                    "Your Digital FTE is running smoothly this week! "
                    "Monitoring emails, messages, and bank transactions on autopilot. "
                    "#AI #Automation #DigitalFTE"
                )
            )
            result = post_facebook_update(f"📊 Weekly Business Update:\n\n{content}", vault_path=vault_path)
            if result.get("dry_run"):
                logger.info("Facebook weekly post — DRY RUN.")
            elif result.get("approval_file"):
                logger.info("Facebook post queued for approval: %s", result["approval_file"])
            else:
                logger.info("Facebook weekly post published — post_id: %s", result.get("post_id"))

        orc.register_schedule(7 * 24 * 3600, _post_facebook_weekly)
        logger.info("Facebook weekly post schedule registered.")
    else:
        logger.info(
            "Facebook weekly post skipped — FACEBOOK_PAGE_ID or FACEBOOK_ACCESS_TOKEN not set."
        )

    # Instagram (requires INSTAGRAM_USER_ID + INSTAGRAM_ACCESS_TOKEN)
    if os.getenv("INSTAGRAM_USER_ID") and os.getenv("INSTAGRAM_ACCESS_TOKEN"):
        from src.skills.instagram_poster import post_instagram_update

        def _post_instagram_weekly() -> None:
            """Post a weekly business caption to Instagram."""
            vault_path = orc.vault_path
            goals_file = vault_path / "Business_Goals.md"
            caption = (
                goals_file.read_text(encoding="utf-8")[:2000]
                if goals_file.exists()
                else (
                    "Weekly business update — your Digital FTE Agent is on duty 24/7. "
                    "#AI #Business #Automation"
                )
            )
            result = post_instagram_update(caption, vault_path=vault_path)
            if result.get("dry_run"):
                logger.info("Instagram weekly post — DRY RUN.")
            elif result.get("approval_file"):
                logger.info("Instagram post queued for approval: %s", result["approval_file"])
            else:
                logger.info("Instagram weekly post published — media_id: %s", result.get("media_id"))

        orc.register_schedule(7 * 24 * 3600, _post_instagram_weekly)
        logger.info("Instagram weekly post schedule registered.")
    else:
        logger.info(
            "Instagram weekly post skipped — INSTAGRAM_USER_ID or INSTAGRAM_ACCESS_TOKEN not set."
        )

    # Twitter/X (requires TWITTER_API_KEY + TWITTER_ACCESS_TOKEN)
    if os.getenv("TWITTER_API_KEY") and os.getenv("TWITTER_ACCESS_TOKEN"):
        from src.skills.twitter_poster import post_twitter_update

        def _post_twitter_weekly() -> None:
            """Post a weekly business tweet."""
            vault_path = orc.vault_path
            result = post_twitter_update(
                "Your Digital FTE is running smoothly this week! "
                "Monitoring emails, messages, and finances on autopilot. "
                "#AI #Automation #DigitalFTE",
                vault_path=vault_path,
            )
            if result.get("dry_run"):
                logger.info("Twitter weekly post — DRY RUN.")
            elif result.get("rate_limited"):
                logger.warning("Twitter weekly post skipped — daily rate limit reached.")
            elif result.get("approval_file"):
                logger.info("Twitter post queued for approval: %s", result["approval_file"])
            else:
                logger.info("Twitter weekly post published — tweet_id: %s", result.get("tweet_id"))

        orc.register_schedule(7 * 24 * 3600, _post_twitter_weekly)
        logger.info("Twitter weekly post schedule registered.")
    else:
        logger.info(
            "Twitter weekly post skipped — TWITTER_API_KEY or TWITTER_ACCESS_TOKEN not set."
        )

    return orc


if __name__ == "__main__":
    logger.info("=== Digital FTE Agent — Local Orchestrator ===")
    logger.info("Vault:   %s", os.getenv("VAULT_PATH", "(not set — run scripts/setup_vault.py)"))
    logger.info("Mode:    %s", os.getenv("AGENT_MODE", "local"))
    logger.info("DRY_RUN: %s", os.getenv("DRY_RUN", "true"))
    build_orchestrator().run()
