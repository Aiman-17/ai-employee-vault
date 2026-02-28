---
name: vault-monitor
description: >
  Process all pending items in Needs_Action/, create Plans, raise approvals,
  and advance each item through the vault lifecycle (claim → plan → approve → done).
  Run this skill whenever you want Claude to actively work through the action queue.
---

# Vault Monitor Skill

## Your Role

You are the Digital FTE's reasoning engine. Your job is to:

1. Read every file in `VAULT_PATH/Needs_Action/`
2. **Claim** each item atomically (move to `In_Progress/claude/`)
3. **Reason** about it using `Business_Goals.md` and `Company_Handbook.md`
4. **Plan** — create a structured `Plans/PLAN_<name>.md`
5. **Gate** — write a `Pending_Approval/` card for every sensitive action
6. **Log** every decision

## Step-by-Step Execution

### Step 1 — Read Vault Context

Before processing anything, read:
- `VAULT_PATH/Business_Goals.md` — what matters this week
- `VAULT_PATH/Company_Handbook.md` — rules of engagement (approval thresholds, known contacts)
- `VAULT_PATH/Dashboard.md` — current state of affairs

### Step 2 — List Needs_Action/

List all `.md` files in `VAULT_PATH/Needs_Action/`. For each file:

### Step 3 — Claim the Item

Move the file from `Needs_Action/<file>` to `In_Progress/claude/<file>` using an atomic rename.

If the rename fails (file already gone), skip — another agent claimed it.

### Step 4 — Read and Classify

Read the YAML front-matter of the claimed file:

| Field | Values |
|-------|--------|
| `type` | `email`, `whatsapp`, `file_drop`, `finance`, `error` |
| `priority` | `high`, `medium`, `low` |
| `status` | `pending` |

### Step 5 — Create Plan

Write `VAULT_PATH/Plans/PLAN_<original_name>.md` with this structure:

```markdown
---
created: <ISO timestamp>
source: <original Needs_Action file>
status: in_progress
---

## Objective
<One sentence: what needs to happen>

## Steps
- [x] Claim item from Needs_Action/
- [ ] <Next concrete step>
- [ ] <Approval gate if needed>
- [ ] Move to Done/

## Dependencies
<Any external info needed>

## Approval Gates
<List every action that needs human sign-off per Company_Handbook.md rules>

## Risk Flags
<Any constitutional constraints (Articles IV, VII, XIII)>
```

### Step 6 — Decide: Auto-execute or Approval Required?

Check `Company_Handbook.md` approval thresholds:

**Auto-approved** (execute without asking):
- Categorising accounting entries
- Generating reports or summaries
- Creating vault documents
- Replying to known contacts (if flagged `auto_reply: true` in Handbook)

**Requires approval** — create `Pending_Approval/<ACTION>_<name>_<date>.md`:
- Sending email to new contacts
- Any payment or financial commitment
- Bulk emails
- Social DMs or replies
- Deleting files outside the vault
- Subscription cancellations

### Step 7 — Write Approval Card (if needed)

```markdown
---
type: approval_request
action: <action_type>
source_file: <filename from In_Progress/>
plan_ref: PLAN_<name>.md
created: <ISO timestamp>
expires: <24h from now>
status: pending
---

## Action: <action_type>

- **What**: <clear description>
- **Why**: <reason from item>
- **Risk**: <any constitutional flags>

## To Approve
Move this file to `Approved/`.

## To Reject
Move this file to `Rejected/`.
```

### Step 8 — Update Dashboard

Append to `## Recent Activity` in `Dashboard.md`:

```
- [<timestamp>] Processed: <item name> → <outcome>
```

### Step 9 — Complete or Wait

- If **no approval needed**: move `In_Progress/claude/<file>` and `Plans/PLAN_<file>` to `Done/`.
- If **approval pending**: leave in `In_Progress/claude/` until `ApprovalHandler` picks up the `Approved/` file.

## Error Handling

- **File unreadable**: write error card to `Needs_Action/PARSE_ERROR_<name>.md` and skip.
- **Constitutional violation detected**: halt immediately; write `Needs_Action/BREACH_<name>.md`.
- **Vault not found**: ask user to run `uv run python scripts/setup_vault.py`.

## Completion Signal

When all files in `Needs_Action/` are processed, output:

```
<promise>TASK_COMPLETE</promise>
```

This signals the Ralph Wiggum Stop hook that the task loop is done.
