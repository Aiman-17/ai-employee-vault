---
name: approval-handler
description: >
  Execute all approved actions in the Approved/ folder, log results, update
  Dashboard, and move all related artifacts to Done/.
  Run after you (the human) have moved approval files from Pending_Approval/ to Approved/.
---

# Approval Handler Skill

## Your Role

The human has reviewed and approved one or more actions. Your job is to:

1. Read every `.md` file in `VAULT_PATH/Approved/`
2. Validate the approval (not expired, well-formed)
3. Execute the approved action via the correct MCP server
4. Log the outcome and update Dashboard
5. Archive all related files to `Done/`

## Step-by-Step Execution

### Step 1 — List Approved/

List all `.md` files in `VAULT_PATH/Approved/`. If empty, report "No pending approvals" and stop.

### Step 2 — Validate Each Approval

For each file, read the YAML front-matter and check:

- `status: pending` (not already processed)
- `expires:` not in the past — if expired, move to `Rejected/` with a note
- `action:` is a known action type

### Step 3 — Execute the Action

Route by `action` field:

#### `file_move`
```
Move: In_Progress/<source_file> → Done/<source_file>
Move: Plans/<plan_ref>           → Done/<plan_ref>
```

#### `email_send`
```
Call: email-mcp → send_email(to, subject, body, attachment)
```
> DRY_RUN guard is active unless DRY_RUN=false in .env

#### `payment`
```
Call: browser-mcp → navigate to payment portal → fill form → confirm
```
> NEVER retry payments automatically — always create a fresh approval if it fails.

#### `social_post`
```
Call: browser-mcp or social API MCP → post content
```

#### `odoo_invoice`
```
Call: odoo-mcp → post_invoice(invoice_id)
```

### Step 4 — Handle Failures Gracefully

If the action fails:

1. **Do NOT** delete the approval file
2. Write `Needs_Action/RETRY_<action>_<timestamp>.md` with:
   - What failed and why (plain English)
   - What the user needs to do to retry
3. Log the failure to `Logs/YYYY-MM-DD.json`
4. Leave the approval file in `Approved/` for manual review

### Step 5 — Archive to Done/

On success:

```
Move: Approved/<approval_file>         → Done/<approval_file>
Move: In_Progress/<source_file>        → Done/<source_file>  (if applicable)
Move: Plans/<plan_ref>                 → Done/<plan_ref>     (if applicable)
```

### Step 6 — Update Dashboard

Append to `## Recent Activity` in `Dashboard.md`:

```
- [<timestamp>] Executed: <action_type> — <brief outcome>
```

### Step 7 — Audit Log

Every executed action must produce a log entry in `Logs/YYYY-MM-DD.json`:

```json
{
  "timestamp": "<ISO>",
  "action_type": "<action>",
  "actor": "approval_handler",
  "target": "<recipient/file>",
  "parameters": {},
  "approval_status": "approved",
  "approved_by": "human",
  "result": "success"
}
```

## Completion Signal

After all approvals are processed:

```
<promise>TASK_COMPLETE</promise>
```

## Constitutional Reminders

- Never execute payment actions that weren't explicitly approved (Article IV.2)
- Never bypass a `ConstitutionalBreachError` — halt and alert human (Article XIII)
- If DRY_RUN=true, log intent but skip real MCP calls (Article VI.2)
- Update Dashboard only if AGENT_MODE=local (Article IX single-writer rule)
