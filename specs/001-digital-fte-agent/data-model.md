# Data Model: Digital FTE Agent

**Branch**: `001-digital-fte-agent` | **Date**: 2026-02-22

---

## Entity Overview

| Entity | Storage Location | Format | Owner |
|--------|-----------------|--------|-------|
| Action Item | `/Needs_Action/<TYPE>_<ID>_<TS>.md` | Markdown + frontmatter | Watcher (writer) |
| Plan | `/Plans/PLAN_<task>_<TS>.md` | Markdown + frontmatter | Claude (writer) |
| Approval Request | `/Pending_Approval/<ACTION>_<target>_<TS>.md` | Markdown + frontmatter | Claude (writer) |
| CEO Briefing | `/Briefings/YYYY-MM-DD_Monday_Briefing.md` | Markdown + frontmatter | Claude (writer) |
| Audit Log Entry | `/Logs/YYYY-MM-DD.json` | JSON array | Claude + MCP (writer) |
| Watcher State | `/State/<watcher_name>.json` | JSON object | Watcher (writer) |
| Alert File | `/Needs_Action/ALERT_<type>_<TS>.md` | Markdown + frontmatter | Watcher/System (writer) |
| Dashboard | `/Dashboard.md` | Markdown | Local agent only (single-writer) |

---

## 1. Action Item

**Location**: `/Needs_Action/<TYPE>_<SOURCE_ID>_<YYYYMMDD_HHMMSS>.md`

**Naming examples**:
- `EMAIL_msg_18a3f2e9_20260222_103045.md`
- `WHATSAPP_chat_client_a_20260222_103120.md`
- `FILE_report_q1.pdf_20260222_091500.md`
- `FINANCE_csv_march2026_20260222_080000.md`

**Schema**:
```yaml
---
type: email | whatsapp | file_drop | finance | alert
source: gmail | whatsapp_web | filesystem | accounting | system
source_id: <unique ID from source system>
from: <sender email, phone, or filename>
subject: <email subject, keyword, or file description>
received: <ISO 8601 timestamp>
priority: high | medium | low
status: pending | claimed | done
claimed_by: local | cloud | null
claimed_at: <ISO 8601 | null>
watcher: gmail_watcher | whatsapp_watcher | filesystem_watcher | finance_watcher
---

## Content

[Event details — email snippet, message text, file metadata, transaction summary]

## Suggested Actions

- [ ] [Action 1]
- [ ] [Action 2]
```

**State transitions**:
```
/Needs_Action/ → (claim-by-move) → /In_Progress/<agent>/ → /Done/
               → (expired/dismissed) → /Rejected/
```

**Constraints**:
- `source_id` must be globally unique within the watcher's state file
- `claimed_by` field set at claim time; no other agent may process a claimed item
- File must be created atomically (write to temp, rename into place)

---

## 2. Plan

**Location**: `/Plans/PLAN_<task_slug>_<YYYYMMDD_HHMMSS>.md`

**Naming example**: `PLAN_invoice_client_a_20260222_104500.md`

**Schema**:
```yaml
---
created: <ISO 8601>
task_ref: <source Action Item filename in /Needs_Action or /In_Progress>
status: draft | in_progress | awaiting_approval | complete | failed
agent: local | cloud
ralph_iteration: <0..10>
max_iterations: 10
last_updated: <ISO 8601>
---

## Objective

[One sentence: what this plan achieves]

## Steps

- [ ] Step 1: [description]
- [ ] Step 2: [description] (REQUIRES APPROVAL)
- [x] Step 3: [completed step]

## Dependencies

- [Dependency 1: file or external system]
- [Dependency 2]

## Approval Gates

- Payment > $0 → MUST create /Pending_Approval/ file
- Email to new contact → MUST create /Pending_Approval/ file

## Risk Flags

- [Risk 1: description and mitigation]
```

**Constraints**:
- Must be created before any multi-step execution begins (FR-010)
- `ralph_iteration` incremented by Stop hook on each re-injection
- At `ralph_iteration == 10`: status → `failed`, partial log written, human notified

---

## 3. Approval Request

**Location**: `/Pending_Approval/<ACTION>_<target_slug>_<YYYYMMDD_HHMMSS>.md`

**Naming examples**:
- `PAYMENT_client_a_20260222_110000.md`
- `EMAIL_invoice_client_a_20260222_110500.md`
- `POST_linkedin_weekly_update_20260222_090000.md`
- `CANCEL_notion_subscription_20260222_150000.md`

**Schema**:
```yaml
---
type: approval_request
action: send_email | post_social | payment | cancel_subscription | bulk_email |
        account_closure | post_invoice | new_payee | deletion_external
target: <recipient email, platform, or service name>
target_id: <account ID, recipient ID, or null>
amount: <decimal | null>
currency: <USD | null>
plan_ref: <Plan.md filename>
created: <ISO 8601>
expires: <ISO 8601 — created + 24h>
status: pending | approved | rejected | expired
---

## Action Details

**Action**: [Human-readable description]
**Target**: [Recipient/Platform]
**Amount**: [$X.XX | N/A]
**Reference**: [Invoice # / Plan reference]

## To Approve

Move this file to `/Approved/` folder.

## To Reject

Move this file to `/Rejected/` folder.

## Auto-expiry

This request expires at [expires timestamp]. If not actioned, it will be
automatically moved to `/Rejected/` and logged.
```

**State transitions**:
```
/Pending_Approval/ → (user moves file) → /Approved/ → [MCP executes] → /Done/
                  → (24h elapsed) → /Rejected/
```

**Constraints**:
- Orchestrator polls `/Approved/` every 30 seconds
- Expiry checker runs every 5 minutes; moves stale files to `/Rejected/`
- Cloud agent may ONLY write to `/Pending_Approval/` — never to `/Approved/`

---

## 4. Audit Log Entry

**Location**: `/Logs/YYYY-MM-DD.json` (one file per day, JSON array)

**Entry schema**:
```json
{
  "timestamp": "2026-02-22T10:45:00Z",
  "action_type": "email_send | social_post | payment_draft | plan_created |
                  approval_granted | approval_expired | watcher_restart |
                  ceo_briefing_generated | file_claimed | file_completed",
  "actor": "local_agent | cloud_agent | gmail_watcher | whatsapp_watcher |
            filesystem_watcher | finance_watcher | orchestrator",
  "target": "<email address | URL | filename | platform>",
  "parameters": {
    "subject": "<if email>",
    "amount": "<if payment>",
    "platform": "<if social post>",
    "file_path": "<if file operation>"
  },
  "approval_status": "approved | auto_approved | not_required | expired",
  "approved_by": "human | system | null",
  "plan_ref": "<Plan.md filename | null>",
  "result": "success | failure | partial",
  "error": "<error message | null>",
  "dry_run": false
}
```

**Constraints**:
- 90-day minimum retention (FR-021)
- `DRY_RUN=true` entries must have `"dry_run": true` — clearly distinguishable
- Log file must be appended atomically (append-only, no overwrites)
- Entries must be written for ALL MCP-executed actions with no exceptions

---

## 5. Watcher State

**Location**: `/State/<watcher_name>.json`

**Files**:
- `/State/gmail_watcher.json`
- `/State/whatsapp_watcher.json`
- `/State/filesystem_watcher.json`
- `/State/finance_watcher.json`

**Schema**:
```json
{
  "watcher": "gmail | whatsapp | filesystem | finance",
  "processed_ids": ["<id1>", "<id2>", "..."],
  "last_updated": "2026-02-22T10:30:00Z",
  "last_successful_check": "2026-02-22T10:28:00Z",
  "error_count": 0,
  "backoff_seconds": 0
}
```

**Constraints**:
- Loaded on watcher startup; saved after each polling cycle
- `processed_ids` compacted after 10,000 entries (drop IDs older than 30 days)
- `backoff_seconds` reflects current exponential backoff state; reset on success
- File written atomically (write to `<name>.tmp`, rename)

---

## 6. CEO Briefing

**Location**: `/Briefings/YYYY-MM-DD_Monday_Briefing.md`

**Schema**:
```yaml
---
generated: <ISO 8601>
period: <YYYY-MM-DD> to <YYYY-MM-DD>
agent: local | cloud
trigger: scheduled | manual
ralph_iterations_used: <0..10>
---

# Monday Morning CEO Briefing

## Executive Summary
[1-2 sentences: overall status and headline metric]

## Revenue

- **This Week**: $X,XXX
- **MTD**: $X,XXX (XX% of $XX,XXX target)
- **Trend**: On track | Behind | Ahead

## Completed Tasks

- [x] Task 1
- [x] Task 2

## Bottlenecks

| Task | Expected | Actual | Delay |
|------|----------|--------|-------|
| Task A | 2 days | 5 days | +3 days |

## Proactive Suggestions

### Cost Optimization
- **[Service]**: [Usage status]. Cost: $X/month. → [ACTION in /Pending_Approval]

### Upcoming Deadlines
- [Project]: Due [date] ([N] days)

## Social Media Summary *(Gold+)*

| Platform | Posts This Week | Engagement | Notes |
|----------|----------------|------------|-------|
| LinkedIn | X | X impressions | |
| Twitter/X | X | X impressions | API limit note if hit |

## Accounting Summary *(Gold+ — Odoo)*

- Draft invoices pending: X
- Payments posted: X
- Revenue booked: $X,XXX
```

---

## 7. Alert File

**Location**: `/Needs_Action/ALERT_<alert_type>_<YYYYMMDD_HHMMSS>.md`

**Naming examples**:
- `ALERT_rate_limit_gmail_20260222_103000.md`
- `ALERT_auth_expiry_gmail_20260222_080000.md`
- `ALERT_wa_session_loss_20260222_110000.md`
- `ALERT_ralph_ceiling_plan_invoice_20260222_120000.md`

**Schema**:
```yaml
---
type: alert
alert_type: rate_limit | auth_expiry | wa_session_loss | ralph_ceiling |
            watcher_crash | vm_unreachable | approval_expiry
source: <watcher_name | orchestrator | ralph_hook>
severity: info | warning | critical
created: <ISO 8601>
status: pending | acknowledged | resolved
email_sent: true | false
---

## Alert: [Human-readable title]

**Severity**: [CRITICAL | WARNING | INFO]
**Source**: [Component name]
**Time**: [timestamp]

## Description

[What happened and why it is an alert]

## Recommended Action

[What the human should do — e.g., "Re-authenticate Gmail OAuth", "Re-scan WhatsApp QR code"]

## Auto-Recovery Status

[Whether system is attempting recovery or requires manual intervention]
```

---

## 8. Dashboard

**Location**: `/Dashboard.md`
**Single-writer rule**: Local agent ONLY. Cloud agent writes to `/Updates/`.

**Schema**:
```yaml
---
last_updated: <ISO 8601>
writer: local_agent
version: <increment on each write>
---

# AI Employee Dashboard

## System Status

| Component | Status | Last Check |
|-----------|--------|-----------|
| Gmail Watcher | ✅ Running | HH:MM |
| WhatsApp Watcher | ✅ Running | HH:MM |
| Filesystem Watcher | ✅ Running | HH:MM |
| Finance Watcher | ✅ Running | HH:MM |
| Cloud Agent | ✅ Online | HH:MM |

## Pending Actions

- X items in /Needs_Action
- X items awaiting approval in /Pending_Approval

## Recent Activity (Last 5 Actions)

- [YYYY-MM-DD HH:MM] [Action description]

## Business Snapshot

- Revenue MTD: $X,XXX / $XX,XXX target
- Tasks completed this week: X
- Open tasks: X
```

---

## State Transition Summary

```
Action Item lifecycle:
  /Needs_Action/ → claim-by-move → /In_Progress/<agent>/ → /Done/
  /Needs_Action/ → (expired or dismissed) → /Rejected/

Approval Request lifecycle:
  /Pending_Approval/ → (user moves) → /Approved/ → [MCP executes] → /Done/
  /Pending_Approval/ → (24h elapsed, orchestrator moves) → /Rejected/

Plan lifecycle:
  /Plans/ [status: draft] → [status: in_progress] → [status: complete]
  /Plans/ [status: in_progress] → [status: failed, ralph_iteration: 10]

Watcher State lifecycle:
  /State/*.json — persistent, append-only, compacted at 10k entries

Audit Log lifecycle:
  /Logs/YYYY-MM-DD.json — append-only, 90-day retention
```
