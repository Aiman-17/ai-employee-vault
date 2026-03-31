"""
src/audit/ceo_briefing.py — Monday Morning CEO Briefing generator.

Generates a structured Briefing Markdown file by:
  1. Reading Business_Goals.md for revenue targets and KPIs.
  2. Parsing Accounting/Current_Month.md for period revenue.
  3. Scanning Done/ for tasks completed in the reporting period.
  4. Running run_subscription_audit() for cost optimisation flags.
  5. Computing bottlenecks (tasks with long elapsed time).
  6. Writing Briefings/YYYY-MM-DD_Monday_Briefing.md.
  7. Writing flagged subscriptions to Pending_Approval/SUBSCRIPTION_*.md (T061).

Usage:
    from src.audit.ceo_briefing import generate_briefing
    from datetime import date, timedelta
    briefing = generate_briefing(vault_path, date.today() - timedelta(7), date.today())
"""

import logging
import os
import re
import time
from datetime import date, datetime, timezone
from pathlib import Path

from src.audit.audit_logic import run_subscription_audit
from src.dry_run import dry_run_guard
from src.vault_utils import update_dashboard

logger = logging.getLogger(__name__)

DEFAULT_MONTHLY_REVENUE_TARGET = float(os.getenv("REVENUE_TARGET", "10000"))


# ── Public entry point ────────────────────────────────────────────────────────

def generate_briefing(
    vault_path: Path,
    period_start: date,
    period_end: date,
) -> Path:
    """
    Generate a Monday Morning CEO Briefing for the given period.

    Args:
        vault_path:    Path to the Obsidian vault root.
        period_start:  Start of reporting period (inclusive).
        period_end:    End of reporting period (inclusive).

    Returns:
        Path to the created Briefings/YYYY-MM-DD_Monday_Briefing.md file.
    """
    logger.info("Generating CEO Briefing for %s → %s", period_start, period_end)

    goals = _read_business_goals(vault_path)
    revenue = _compute_period_revenue(vault_path, period_start, period_end)
    completed_tasks = _scan_completed_tasks(vault_path, period_start, period_end)
    audit = run_subscription_audit(vault_path)
    _write_subscription_approval_cards(vault_path, audit)   # T061
    bottlenecks = _compute_bottlenecks(vault_path, period_start, period_end)

    briefing_path = _write_briefing(
        vault_path, period_start, period_end,
        goals, revenue, completed_tasks, audit, bottlenecks,
    )

    update_dashboard(
        vault_path,
        f"CEO Briefing generated: [[{briefing_path.name}]] (Revenue: ${revenue:.2f})",
    )
    logger.info("CEO Briefing written: %s", briefing_path)
    return briefing_path


# ── Business Goals reader ─────────────────────────────────────────────────────

def _read_business_goals(vault_path: Path) -> dict:
    """Parse revenue target and MTD from Business_Goals.md. Returns defaults if absent."""
    defaults: dict = {
        "monthly_target": DEFAULT_MONTHLY_REVENUE_TARGET,
        "current_mtd": 0.0,
        "raw_text": "",
    }
    goals_file = vault_path / "Business_Goals.md"
    if not goals_file.exists():
        logger.info("Business_Goals.md not found — using revenue target defaults.")
        return defaults

    text = goals_file.read_text(encoding="utf-8")
    defaults["raw_text"] = text[:3000]

    m = re.search(r"[Mm]onthly\s+goal[:\s]+\$?([\d,]+)", text)
    if m:
        try:
            defaults["monthly_target"] = float(m.group(1).replace(",", ""))
        except ValueError:
            pass

    m = re.search(r"[Cc]urrent\s+MTD[:\s]+\$?([\d,]+)", text)
    if m:
        try:
            defaults["current_mtd"] = float(m.group(1).replace(",", ""))
        except ValueError:
            pass

    return defaults


# ── Accounting parser ─────────────────────────────────────────────────────────

def _compute_period_revenue(vault_path: Path, start: date, end: date) -> float:
    """Sum credit (positive) transactions in Accounting/Current_Month.md for the period."""
    accounting_file = vault_path / "Accounting" / "Current_Month.md"
    if not accounting_file.exists():
        logger.info("Accounting/Current_Month.md not found — revenue set to 0.")
        return 0.0

    total = 0.0
    try:
        text = accounting_file.read_text(encoding="utf-8")
        for line in text.splitlines():
            cells = _parse_md_row(line)
            if cells is None or len(cells) < 2:
                continue
            date_str, amount_str = cells[0], cells[1]
            try:
                tx_date = date.fromisoformat(date_str.strip())
            except ValueError:
                continue
            if not (start <= tx_date <= end):
                continue
            try:
                amount = float(amount_str.strip().replace(",", "").replace("$", "").replace("€", ""))
            except ValueError:
                continue
            if amount > 0:
                total += amount
    except Exception as exc:
        logger.warning("Error parsing accounting file: %s", exc)

    return total


def _parse_md_row(line: str) -> list[str] | None:
    """Parse a Markdown table data row. Returns cell list or None."""
    stripped = line.strip()
    if not stripped.startswith("|") or "---" in stripped:
        return None
    cells = [c.strip() for c in stripped.strip("|").split("|")]
    if len(cells) < 2 or cells[0].lower() in ("date", ""):
        return None
    return cells


# ── Done/ task scanner ────────────────────────────────────────────────────────

def _scan_completed_tasks(vault_path: Path, start: date, end: date) -> list[str]:
    """Return titles of .md files in Done/ whose mtime falls within the period."""
    done_dir = vault_path / "Done"
    if not done_dir.exists():
        return []

    completed: list[str] = []
    for f in done_dir.glob("*.md"):
        try:
            mtime = date.fromtimestamp(f.stat().st_mtime)
            if start <= mtime <= end:
                completed.append(_extract_task_title(f))
        except Exception:
            continue
    return completed


def _extract_task_title(task_file: Path) -> str:
    """Extract a human-readable title from a vault .md file."""
    try:
        text = task_file.read_text(encoding="utf-8", errors="replace")
        for line in text.splitlines():
            if line.startswith("## ") or line.startswith("# "):
                return line.lstrip("#").strip()
        name = task_file.stem
        for prefix in ("EMAIL_", "WHATSAPP_", "FILE_", "PLAN_", "RETRY_", "ALERT_"):
            name = name.replace(prefix, "")
        return name
    except Exception:
        return task_file.stem


# ── Bottleneck detector ───────────────────────────────────────────────────────

def _compute_bottlenecks(vault_path: Path, start: date, end: date) -> list[dict]:
    """
    Identify Done/ tasks that took longer than TARGET_DAYS to complete.
    Returns list of {task, expected_days, actual_days, delay_days} dicts.
    """
    done_dir = vault_path / "Done"
    if not done_dir.exists():
        return []

    TARGET_DAYS = 2
    bottlenecks: list[dict] = []
    in_progress_dir = vault_path / "In_Progress" / "claude"

    for done_file in done_dir.glob("*.md"):
        try:
            done_time = date.fromtimestamp(done_file.stat().st_mtime)
            if not (start <= done_time <= end):
                continue

            in_progress_candidate = in_progress_dir / done_file.name
            if in_progress_candidate.exists():
                start_time = date.fromtimestamp(in_progress_candidate.stat().st_mtime)
            else:
                start_time = date.fromtimestamp(done_file.stat().st_ctime)

            elapsed = (done_time - start_time).days
            if elapsed > TARGET_DAYS:
                bottlenecks.append({
                    "task": _extract_task_title(done_file),
                    "expected_days": TARGET_DAYS,
                    "actual_days": elapsed,
                    "delay_days": elapsed - TARGET_DAYS,
                })
        except Exception:
            continue

    return bottlenecks


# ── Subscription approval cards (T061) ───────────────────────────────────────

def _write_subscription_approval_cards(vault_path: Path, audit: dict) -> None:
    """
    Write Pending_Approval/SUBSCRIPTION_<vendor>_<date>.md for each flagged
    subscription so the human can review and approve cancellation. (T061)
    """
    subscriptions = audit.get("subscriptions", [])
    if not subscriptions:
        return

    if dry_run_guard("subscription_card", audit, actor="ceo_briefing"):
        logger.info("[DRY RUN] Subscription approval cards skipped.")
        return

    approval_dir = vault_path / "Pending_Approval"
    approval_dir.mkdir(parents=True, exist_ok=True)

    today_str = date.today().isoformat()

    for sub in subscriptions:
        vendor_slug = re.sub(r"[^a-z0-9]+", "_", sub["name"].lower()).strip("_")
        card_path = approval_dir / f"SUBSCRIPTION_{vendor_slug}_{today_str}.md"
        if card_path.exists():
            continue  # Already written today

        card_path.write_text(
            f"---\n"
            f"type: subscription_review\n"
            f"action: cancel_subscription\n"
            f"vendor: {sub['name']}\n"
            f"monthly_cost: {abs(sub['amount']):.2f}\n"
            f"status: pending\n"
            f"created: {datetime.now(tz=timezone.utc).isoformat()}\n"
            f"---\n\n"
            f"## Subscription Review: {sub['name']}\n\n"
            f"Your Digital FTE has flagged this subscription for review.\n\n"
            f"| Field | Value |\n"
            f"|-------|-------|\n"
            f"| Service | {sub['name']} |\n"
            f"| Monthly Cost | ${abs(sub['amount']):.2f} |\n"
            f"| Last Seen | {sub.get('date', today_str)} |\n\n"
            f"## To Cancel\n"
            f"Move this file to `/Approved` to proceed with cancellation research.\n\n"
            f"## To Keep\n"
            f"Move this file to `/Rejected` to dismiss this suggestion.\n",
            encoding="utf-8",
        )
        logger.info("Subscription approval card written: %s", card_path.name)


# ── Briefing renderer ─────────────────────────────────────────────────────────

def _write_briefing(
    vault_path: Path,
    period_start: date,
    period_end: date,
    goals: dict,
    revenue: float,
    completed_tasks: list[str],
    audit: dict,
    bottlenecks: list[dict],
) -> Path:
    """Render the CEO Briefing Markdown and write to Briefings/."""
    briefings_dir = vault_path / "Briefings"
    briefings_dir.mkdir(parents=True, exist_ok=True)

    today_str = date.today().isoformat()
    briefing_file = briefings_dir / f"{today_str}_Monday_Briefing.md"

    monthly_target = goals["monthly_target"]
    mtd = goals.get("current_mtd") or revenue
    pct = (mtd / monthly_target * 100) if monthly_target > 0 else 0.0
    trend = "On track" if pct >= 40 else "Behind target"

    if pct >= 80:
        exec_summary = "Strong week — revenue on track, minimal bottlenecks."
    elif pct >= 50:
        exec_summary = "Moderate week — revenue progressing; review bottlenecks."
    else:
        exec_summary = "Attention needed — revenue below target; cost review recommended."

    tasks_section = (
        "\n".join(f"- [x] {t}" for t in completed_tasks)
        or "_No tasks completed this week._"
    )

    if bottlenecks:
        btn_rows = "\n".join(
            f"| {b['task'][:40]} | {b['expected_days']}d | {b['actual_days']}d | +{b['delay_days']}d |"
            for b in bottlenecks
        )
        bottlenecks_section = (
            "| Task | Expected | Actual | Delay |\n"
            "|------|----------|--------|-------|\n"
            + btn_rows
        )
    else:
        bottlenecks_section = "_No bottlenecks detected this week._"

    cost_lines = []
    for sub in audit.get("subscriptions", []):
        cost_lines.append(
            f"- **{sub['name']}**: ${abs(sub['amount']):.2f}/month\n"
            f"  - [ACTION] Review subscription? See `Pending_Approval/SUBSCRIPTION_{re.sub(r'[^a-z0-9]+','_',sub['name'].lower()).strip('_')}_{today_str}.md`"
        )
    for lp in audit.get("large_payments", []):
        cost_lines.append(
            f"- **Large payment**: {lp['name']} — ${abs(lp['amount']):.2f} on {lp.get('date', '?')}"
        )
    cost_section = "\n".join(cost_lines) or "_No cost anomalies detected._"

    content = (
        f"---\n"
        f"generated: {datetime.now(tz=timezone.utc).isoformat()}\n"
        f"period: {period_start.isoformat()} to {period_end.isoformat()}\n"
        f"---\n\n"
        f"# Monday Morning CEO Briefing\n\n"
        f"## Executive Summary\n\n"
        f"{exec_summary}\n\n"
        f"## Revenue\n\n"
        f"- **This Week**: ${revenue:.2f}\n"
        f"- **MTD**: ${mtd:.2f} ({pct:.0f}% of ${monthly_target:,.0f} target)\n"
        f"- **Trend**: {trend}\n\n"
        f"## Completed Tasks\n\n"
        f"{tasks_section}\n\n"
        f"## Bottlenecks\n\n"
        f"{bottlenecks_section}\n\n"
        f"## Proactive Suggestions\n\n"
        f"_Review the Cost Optimization section and approve or reject each item._\n\n"
        f"## Cost Optimization\n\n"
        f"{cost_section}\n\n"
        f"---\n"
        f"*Generated by Digital FTE Agent v1.0 — period {period_start} to {period_end}*\n"
    )

    briefing_file.write_text(content, encoding="utf-8")
    return briefing_file
