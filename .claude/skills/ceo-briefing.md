---
name: ceo-briefing
description: Generate the Monday Morning CEO Briefing for a given reporting period. Reads Business_Goals.md, Accounting/Current_Month.md, Done/ tasks, and subscription audit data to produce a structured briefing with revenue, bottlenecks, and cost optimisation flags.
---

## CEO Briefing Skill

Generate a Monday Morning CEO Briefing and subscription approval cards.

### Trigger

Runs every Sunday night via the Orchestrator's weekly schedule.
Manual invocation is also supported (see below).

### Manual usage

```python
from pathlib import Path
from datetime import date, timedelta
from src.audit.ceo_briefing import generate_briefing

vault_path = Path("path/to/vault")
briefing = generate_briefing(vault_path, date.today() - timedelta(7), date.today())
print(f"Briefing written: {briefing}")
```

Or from the command line:

```bash
uv run python -c "
from pathlib import Path; import os
from datetime import date, timedelta
from src.audit.ceo_briefing import generate_briefing
vp = Path(os.environ['VAULT_PATH'])
print(generate_briefing(vp, date.today() - timedelta(7), date.today()))
"
```

### Output artifacts

| Artifact | Path |
|----------|------|
| CEO Briefing Markdown | `Briefings/YYYY-MM-DD_Monday_Briefing.md` |
| Subscription review cards | `Pending_Approval/SUBSCRIPTION_<vendor>_<date>.md` |

### Briefing sections

1. **Executive Summary** — one-line status based on revenue percentage of target
2. **Revenue** — this week's total, MTD, and % of monthly goal
3. **Completed Tasks** — all `Done/` files whose `mtime` falls within the reporting period
4. **Bottlenecks** — tasks that exceeded the 2-day completion target
5. **Proactive Suggestions** — prompt to review the Cost Optimisation section
6. **Cost Optimisation** — subscriptions and large payments flagged by the subscription audit

### Human-in-the-Loop (subscription cards)

When the subscription audit flags recurring charges, approval cards are written to `Pending_Approval/`.

- Move card to `Approved/` → proceed with cancellation research
- Move card to `Rejected/` → dismiss suggestion for this period

Cards are idempotent — only one card per vendor per day is created.

### Environment variables

| Variable | Default | Purpose |
|----------|---------|---------|
| `VAULT_PATH` | `.` | Obsidian vault root |
| `REVENUE_TARGET` | `10000` | Monthly revenue target (USD) |
| `DRY_RUN` | `true` | When `true`, skips writing subscription cards |

### Prerequisites

- `Business_Goals.md` in vault root (optional — defaults used if absent)
- `Accounting/Current_Month.md` Markdown table with `date` and `amount` columns
- `Done/` folder populated by Watcher scripts or agent actions
