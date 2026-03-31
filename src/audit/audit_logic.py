"""
src/audit/audit_logic.py — Subscription detection and business audit logic.

Used by FinanceWatcher (Silver) and the CEO Briefing generator (Gold) to:
  - Identify recurring subscription charges in bank transactions.
  - Flag unusually large or unexpected payments.
  - Generate audit summaries for the Monday Morning CEO Briefing.

Design:
  - SUBSCRIPTION_PATTERNS: domain → human-readable service name mapping.
  - analyze_transaction(): stateless, pure function — safe to call in a loop.
  - run_subscription_audit(): reads Accounting/Current_Month.md and returns
    a structured dict for the CEO Briefing skill to render.
"""

import logging
import os
import re
from pathlib import Path

logger = logging.getLogger(__name__)

# ── Subscription patterns ─────────────────────────────────────────────────────
# Maps lowercase substrings found in transaction descriptions → service name.
# Add your own subscriptions here.

SUBSCRIPTION_PATTERNS: dict[str, str] = {
    # Streaming / entertainment
    "netflix": "Netflix",
    "spotify": "Spotify",
    "apple.com/bill": "Apple Subscriptions",
    "apple music": "Apple Music",
    "youtube premium": "YouTube Premium",
    "amazon prime": "Amazon Prime",
    "disney+": "Disney+",
    "disneyplus": "Disney+",
    "hbo": "HBO Max",
    "paramount": "Paramount+",
    # Productivity / SaaS
    "notion.so": "Notion",
    "notion team": "Notion",
    "notion": "Notion",
    "slack": "Slack",
    "atlassian": "Atlassian (Jira/Confluence)",
    "github": "GitHub",
    "figma": "Figma",
    "canva": "Canva",
    "adobe": "Adobe Creative Cloud",
    "microsoft 365": "Microsoft 365",
    "office 365": "Microsoft 365",
    "dropbox": "Dropbox",
    "google workspace": "Google Workspace",
    "gsuite": "Google Workspace",
    "zoom": "Zoom",
    "loom": "Loom",
    "linear": "Linear",
    "clickup": "ClickUp",
    "monday.com": "Monday.com",
    "airtable": "Airtable",
    "webflow": "Webflow",
    "shopify": "Shopify",
    "intercom": "Intercom",
    "hubspot": "HubSpot",
    "mailchimp": "Mailchimp",
    "sendgrid": "SendGrid",
    # AI / Developer tools
    "openai": "OpenAI (ChatGPT / API)",
    "anthropic": "Anthropic (Claude)",
    "github copilot": "GitHub Copilot",
    "cursor": "Cursor IDE",
    "replit": "Replit",
    "vercel": "Vercel",
    "netlify": "Netlify",
    "heroku": "Heroku",
    "digitalocean": "DigitalOcean",
    "aws": "Amazon Web Services",
    "azure": "Microsoft Azure",
    "gcp": "Google Cloud Platform",
    # Finance / Banking tools
    "quickbooks": "QuickBooks",
    "xero": "Xero",
    "freshbooks": "FreshBooks",
    "stripe": "Stripe",
    "wise": "Wise (transfer fee)",
    "paypal": "PayPal",
}

# Transactions above this threshold trigger a 'large_payment' flag
LARGE_PAYMENT_THRESHOLD = float(os.getenv("LARGE_PAYMENT_THRESHOLD", "500"))


# ── Core analysis function ────────────────────────────────────────────────────

def analyze_transaction(transaction: dict) -> dict | None:
    """
    Analyse a single transaction dict for subscription or large-payment flags.

    Args:
        transaction: dict with at least 'description' and 'amount' keys.
            - description (str): merchant name / narrative
            - amount (str | float): signed amount (negative = debit)
            - date (str, optional): transaction date

    Returns:
        Analysis dict if the transaction is flagged, or None if it looks routine.
        Analysis dict keys:
            type   : 'subscription' | 'large_payment' | 'recurring'
            name   : human-readable service / payee name
            amount : float amount
            description: original description
            flag   : short flag label for display
    """
    description = str(transaction.get("description", "")).lower()
    amount_raw = str(transaction.get("amount", "0")).replace(",", "").replace("$", "").replace("€", "").replace("£", "")
    try:
        amount = float(amount_raw)
    except ValueError:
        amount = 0.0

    # Check subscription patterns
    for pattern, service_name in SUBSCRIPTION_PATTERNS.items():
        if pattern.lower() in description:
            return {
                "type": "subscription",
                "name": service_name,
                "amount": amount,
                "description": transaction.get("description", ""),
                "flag": "Subscription",
            }

    # Large payment flag (debit > threshold)
    if amount < 0 and abs(amount) >= LARGE_PAYMENT_THRESHOLD:
        return {
            "type": "large_payment",
            "name": _extract_payee(description),
            "amount": amount,
            "description": transaction.get("description", ""),
            "flag": f"Large Payment (≥${LARGE_PAYMENT_THRESHOLD:.0f})",
        }

    return None


# ── Subscription audit (for CEO Briefing) ────────────────────────────────────

def run_subscription_audit(vault_path: Path | None = None) -> dict:
    """
    Read Accounting/Current_Month.md and produce a subscription audit summary.

    Returns a dict:
        {
            "subscriptions": [{"name": str, "amount": float, "date": str}, ...],
            "total_monthly_spend": float,
            "flagged_count": int,
            "large_payments": [{"name": str, "amount": float, "date": str}, ...],
        }
    """
    if vault_path is None:
        vault_env = os.getenv("VAULT_PATH", "")
        vault_path = Path(vault_env) if vault_env else Path(".")

    accounting_file = vault_path / "Accounting" / "Current_Month.md"

    subscriptions: list[dict] = []
    large_payments: list[dict] = []

    if not accounting_file.exists():
        logger.info("Accounting/Current_Month.md not found — skipping subscription audit.")
        return {
            "subscriptions": subscriptions,
            "total_monthly_spend": 0.0,
            "flagged_count": 0,
            "large_payments": large_payments,
        }

    # Parse the Markdown table rows
    text = accounting_file.read_text(encoding="utf-8")
    for line in text.splitlines():
        row = _parse_md_table_row(line)
        if row is None:
            continue
        date, amount_str, description = row
        transaction = {"date": date, "amount": amount_str, "description": description}
        analysis = analyze_transaction(transaction)
        if analysis is None:
            continue
        if analysis["type"] == "subscription":
            subscriptions.append({
                "name": analysis["name"],
                "amount": analysis["amount"],
                "date": date,
            })
        elif analysis["type"] == "large_payment":
            large_payments.append({
                "name": analysis["name"],
                "amount": analysis["amount"],
                "date": date,
            })

    total_spend = sum(abs(s["amount"]) for s in subscriptions)

    return {
        "subscriptions": subscriptions,
        "total_monthly_spend": total_spend,
        "flagged_count": len(subscriptions) + len(large_payments),
        "large_payments": large_payments,
    }


# ── Helpers ───────────────────────────────────────────────────────────────────

def _extract_payee(description: str) -> str:
    """
    Attempt to extract a clean payee name from a raw bank description string.
    Falls back to the first 40 characters of the description.
    """
    # Strip common bank prefixes
    cleaned = re.sub(r"^(POS |SQ \*|TST\* |PP\*)", "", description, flags=re.IGNORECASE)
    cleaned = cleaned.strip().split("  ")[0]  # Bank reference often after double space
    return cleaned[:40] if cleaned else "Unknown Payee"


def _parse_md_table_row(line: str) -> tuple[str, str, str] | None:
    """
    Parse a Markdown table row of the form:
        | Date | Amount | Description |
    Returns (date, amount, description) or None if not a data row.
    """
    stripped = line.strip()
    if not stripped.startswith("|") or "---" in stripped:
        return None
    cells = [c.strip() for c in stripped.strip("|").split("|")]
    if len(cells) < 3:
        return None
    date, amount, description = cells[0], cells[1], " | ".join(cells[2:])
    # Skip header row
    if date.lower() in ("date", ""):
        return None
    return date, amount, description
