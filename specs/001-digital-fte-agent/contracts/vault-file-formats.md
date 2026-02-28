# Contract: Vault File Formats

**Branch**: `001-digital-fte-agent` | **Date**: 2026-02-22

This document defines the canonical file naming conventions, frontmatter schemas, and
body structure for every file type that lives in the Obsidian vault. All Watchers,
Claude agents (local and cloud), MCP servers, and the Orchestrator MUST conform to these
contracts. Deviation is a constitutional violation (Article III — Deterministic Auditability).

---

## Naming Convention

```
<TYPE>_<SOURCE_ID_SLUG>_<YYYYMMDD_HHMMSS>.md
```

- `TYPE`: uppercase prefix identifying the entity class (EMAIL, WHATSAPP, FILE, FINANCE,
  PLAN, PAYMENT, POST, CANCEL, ALERT, BRIEFING)
- `SOURCE_ID_SLUG`: sanitized, lowercase, hyphen-separated identifier from source system
  (max 40 chars; strip special characters; truncate with `...` if needed)
- `YYYYMMDD_HHMMSS`: UTC timestamp at file creation time

**Examples**:
```
EMAIL_msg-18a3f2e9_20260222_103045.md       ← Gmail message ID (truncated)
WHATSAPP_client-a-+971501234567_20260222_103120.md
FILE_q1-sales-report.pdf_20260222_091500.md
FINANCE_march-2026-statement_20260222_080000.md
PLAN_invoice-client-a_20260222_104500.md
PAYMENT_client-a-invoice-1234_20260222_110000.md
POST_linkedin-weekly-update_20260222_090000.md
ALERT_rate-limit-gmail_20260222_103000.md
```

---

## Required Frontmatter Fields by Type

### ACTION ITEM (`/Needs_Action/` and `/In_Progress/`)

```yaml
---
type: email | whatsapp | file_drop | finance | alert
source: gmail | whatsapp_web | filesystem | accounting | system
source_id: <exact ID from source — used for idempotency>
from: <string — sender, phone number, or filename>
subject: <string — subject, keyword match, or file description>
received: <ISO 8601 UTC>
priority: high | medium | low
status: pending | claimed | done
claimed_by: local | cloud | null
claimed_at: <ISO 8601 UTC | null>
watcher: gmail_watcher | whatsapp_watcher | filesystem_watcher | finance_watcher
---
```

**Required body sections**:
```markdown
## Content
[Event details]

## Suggested Actions
- [ ] [Action]
```

### PLAN (`/Plans/`)

```yaml
---
type: plan
created: <ISO 8601 UTC>
task_ref: <Action Item filename — includes folder path>
status: draft | in_progress | awaiting_approval | complete | failed
agent: local | cloud
ralph_iteration: <integer 0..10>
max_iterations: 10
last_updated: <ISO 8601 UTC>
---
```

**Required body sections**: Objective, Steps (checkboxes), Dependencies, Approval Gates,
Risk Flags

### APPROVAL REQUEST (`/Pending_Approval/`)

```yaml
---
type: approval_request
action: send_email | post_social | payment | cancel_subscription | bulk_email |
        account_closure | post_invoice | new_payee | deletion_external
target: <string>
target_id: <string | null>
amount: <decimal | null>
currency: <string | null>
plan_ref: <Plan filename>
created: <ISO 8601 UTC>
expires: <ISO 8601 UTC — exactly 24h after created>
status: pending | approved | rejected | expired
---
```

**Required body sections**: Action Details, To Approve (instructions), To Reject
(instructions), Auto-expiry notice

### CEO BRIEFING (`/Briefings/`)

```yaml
---
type: ceo_briefing
generated: <ISO 8601 UTC>
period_start: <YYYY-MM-DD>
period_end: <YYYY-MM-DD>
agent: local | cloud
trigger: scheduled | manual
ralph_iterations_used: <integer 0..10>
---
```

**Required body sections**: Executive Summary, Revenue, Completed Tasks, Bottlenecks
(table), Proactive Suggestions

### ALERT FILE (`/Needs_Action/ALERT_*`)

```yaml
---
type: alert
alert_type: rate_limit | auth_expiry | wa_session_loss | ralph_ceiling |
            watcher_crash | vm_unreachable | approval_expiry
source: <component name>
severity: info | warning | critical
created: <ISO 8601 UTC>
status: pending | acknowledged | resolved
email_sent: true | false
---
```

**Required body sections**: Alert description, Recommended Action, Auto-Recovery Status

---

## JSON File Schemas

### Audit Log (`/Logs/YYYY-MM-DD.json`)

File is a JSON array; each entry appended on a new line (newline-delimited JSON / NDJSON):

```json
{"timestamp":"ISO8601","action_type":"string","actor":"string","target":"string",
 "parameters":{},"approval_status":"string","approved_by":"string|null",
 "plan_ref":"string|null","result":"success|failure|partial","error":"string|null",
 "dry_run":false}
```

**`action_type` allowed values**:
`email_send`, `email_draft`, `social_post`, `payment_draft`, `calendar_event`,
`plan_created`, `approval_granted`, `approval_expired`, `approval_rejected`,
`watcher_restart`, `ceo_briefing_generated`, `file_claimed`, `file_completed`,
`file_rejected`, `odoo_draft_created`, `odoo_posted`, `alert_written`, `alert_email_sent`

### Watcher State (`/State/<name>.json`)

```json
{
  "watcher": "gmail_watcher",
  "processed_ids": ["id1", "id2"],
  "last_updated": "ISO8601",
  "last_successful_check": "ISO8601",
  "error_count": 0,
  "backoff_seconds": 0
}
```

---

## Validation Rules

| Rule | Description |
|------|-------------|
| Atomic writes | All file writes: write to `<name>.tmp`, then `os.rename()` to final path |
| UTF-8 encoding | All files must be UTF-8 encoded |
| ISO 8601 UTC | All timestamps: `YYYY-MM-DDTHH:MM:SSZ` format (no timezone offset) |
| No secrets | No API keys, tokens, passwords, or session data in any vault file |
| Unique source_id | `source_id` must be unique within the watcher's `/State/*.json` |
| Expiry precision | Approval requests expire exactly 24h after `created` timestamp |
| Log append-only | `/Logs/*.json` — never overwrite; append entries only |
| Single writer Dashboard | Only Local agent writes `/Dashboard.md`; Cloud writes to `/Updates/` |
