# Feature Specification: Digital FTE Agent — Personal AI Employee

**Feature Branch**: `001-digital-fte-agent`
**Created**: 2026-02-22
**Status**: Draft
**Tier Target**: Platinum (all tiers delivered incrementally)

---

## User Scenarios & Testing *(mandatory)*

### User Story 1 — Vault Foundation & File Watcher (Priority: P1) 🎯 Bronze MVP

As a user, I want an Obsidian vault set up as my AI Employee's brain so that
Claude can read tasks from `/Needs_Action` and write reports to the vault
autonomously, even when I am not actively prompting it.

**Why this priority**: This is the minimum viable foundation. Without the vault
and at least one working watcher, no other tier is possible. It demonstrates the
core loop: Watcher → Vault → Claude → Output.

**Independent Test**: Drop a file into the watch folder. Verify a corresponding
`.md` file appears in `/Needs_Action` within 60 seconds. Then trigger Claude to
read and respond to it — confirming the full perception–reasoning loop works.

**Acceptance Scenarios**:

1. **Given** the Obsidian vault exists with `Dashboard.md`, `Company_Handbook.md`,
   `/Inbox`, `/Needs_Action`, `/Done` folders,
   **When** a new file is dropped into the monitored drop folder,
   **Then** the File System Watcher creates a structured `.md` action item in
   `/Needs_Action` within 60 seconds.

2. **Given** a `.md` file exists in `/Needs_Action`,
   **When** Claude is triggered (manually or scheduled),
   **Then** Claude reads the file, produces a response or plan, and writes output
   back to the vault without human guidance.

3. **Given** Claude has processed an action item,
   **When** the task is complete,
   **Then** the item is moved to `/Done` and `Dashboard.md` reflects the update.

4. **Given** the Gmail Watcher or File Watcher crashes,
   **When** the process manager detects the crash,
   **Then** the watcher is automatically restarted within 60 seconds and a log
   entry is written.

---

### User Story 2 — Multi-Watcher & MCP Action Layer (Priority: P2) — Silver

As a user, I want the AI Employee to monitor my Gmail and WhatsApp simultaneously
and take real external actions (send email, post to LinkedIn) via MCP servers,
with a human-approval gate for sensitive actions.

**Why this priority**: Extends the Bronze foundation to real communication
channels. The HITL approval workflow is the primary safety mechanism for all
external actions — it must be proven before any autonomous sends are allowed.

**Independent Test**: Send an email to your Gmail account with "invoice" in the
subject. Verify a `/Needs_Action/EMAIL_*.md` file appears within 3 minutes.
Verify Claude creates a `/Pending_Approval/` approval file for any proposed reply.
Move the approval file to `/Approved`. Verify the email is sent via MCP and the
task moves to `/Done`.

**Acceptance Scenarios**:

1. **Given** the Gmail Watcher is running,
   **When** an unread, important email arrives,
   **Then** a structured action file appears in `/Needs_Action` within 3 minutes,
   containing sender, subject, snippet, and suggested actions.

2. **Given** a WhatsApp message contains a trigger keyword (invoice, urgent,
   payment, help),
   **When** the WhatsApp Watcher detects it,
   **Then** an action file appears in `/Needs_Action` within 90 seconds.

3. **Given** Claude determines a reply or email send is required,
   **When** the recipient is known and the action is pre-approved in
   `Company_Handbook.md`,
   **Then** Claude creates a `/Pending_Approval/*.md` file with full action
   details and waits — it does NOT send autonomously.

4. **Given** an approval file exists in `/Pending_Approval/`,
   **When** the user moves it to `/Approved/`,
   **Then** the MCP server executes the action (send email, post), logs the
   result to `/Logs/YYYY-MM-DD.json`, and moves all related files to `/Done`.

5. **Given** a scheduled trigger fires (cron/Task Scheduler),
   **When** Claude posts a pre-approved LinkedIn update,
   **Then** the post is published via MCP and the action is logged with timestamp
   and content summary.

---

### User Story 3 — Autonomous Business Audit & CEO Briefing (Priority: P3) — Gold

As a business owner, I want Claude to autonomously audit my business every Sunday
night and produce a "Monday Morning CEO Briefing" in Obsidian highlighting revenue,
bottlenecks, and cost-saving suggestions.

**Why this priority**: This is the standout hackathon feature that proves the
agent is proactive rather than reactive. It requires cross-domain integration
(comms + accounting + tasks) and the Ralph Wiggum loop for unattended execution.

**Independent Test**: Place sample `Bank_Transactions.md` and `Business_Goals.md`
files in the vault. Trigger the audit manually. Verify a `Briefings/YYYY-MM-DD_Monday_Briefing.md`
file is generated within 10 minutes with all required sections populated and at
least one cost-saving suggestion.

**Acceptance Scenarios**:

1. **Given** `Business_Goals.md` and `/Accounting/Current_Month.md` exist in vault,
   **When** the Sunday-night scheduled audit runs,
   **Then** Claude reads both files, cross-references completed tasks in `/Done`,
   and writes a CEO Briefing with: Executive Summary, Revenue vs Target, Completed
   Tasks, Bottlenecks table, and Proactive Suggestions.

2. **Given** bank transactions contain subscription charges,
   **When** the audit logic identifies a subscription unused for ≥ 30 days,
   **Then** a cost-saving suggestion is included in the briefing with a
   `/Pending_Approval/CANCEL_*.md` file created for user action.

3. **Given** the audit is a multi-step task,
   **When** Claude reaches a step it cannot complete,
   **Then** the Ralph Wiggum loop re-injects the prompt (up to 10 iterations)
   until either all steps are complete or the iteration ceiling is reached, at
   which point a failure log is written.

4. **Given** cross-domain integrations are active (Odoo ERP + Facebook + Twitter/X),
   **When** the audit runs,
   **Then** accounting data from Odoo and social engagement summaries from
   Facebook/Twitter are included in the CEO Briefing sections.

5. **Given** an audit task is claimed by moving it to `/In_Progress/local/`,
   **When** another process or agent checks `/Needs_Action`,
   **Then** the claimed task is not picked up again (claim-by-move rule enforced).

---

### User Story 4 — Always-On Cloud + Local Agent Separation (Priority: P4) — Platinum

As a user, I want a Cloud agent running 24/7 to triage my email and draft replies
even when my local machine is offline, with Local agent retaining exclusive
authority over all final sends, payments, and WhatsApp actions.

**Why this priority**: Platinum tier proves the system is production-grade. The
cloud/local separation and vault sync model is the most architecturally complex
deliverable and demonstrates real agent-to-agent coordination via file handoffs.

**Independent Test (Minimum Passing Gate)**: With local machine offline, send an
email to the monitored account. When local returns online and syncs the vault,
verify: (a) Cloud's draft reply exists in `/Updates/`, (b) `/Pending_Approval/`
file was created by Cloud, (c) user can approve, (d) Local sends via MCP, (e)
task moves to `/Done`.

**Acceptance Scenarios**:

1. **Given** the Cloud agent is running on a VM (Oracle/AWS),
   **When** an email arrives while Local is offline,
   **Then** Cloud drafts a reply and writes it to `/Updates/EMAIL_draft_*.md` and
   creates `/Pending_Approval/EMAIL_reply_*.md` — it does NOT send.

2. **Given** Local agent comes back online and vault syncs (via Git/Syncthing),
   **When** Local detects a new file in `/Pending_Approval/`,
   **Then** Local presents it to the user; upon approval, Local executes send via
   MCP, logs, and moves to `/Done`.

3. **Given** both Cloud and Local are running simultaneously,
   **When** both detect the same item in `/Needs_Action/<domain>/`,
   **Then** only the first agent to move the item to `/In_Progress/<agent>/`
   processes it; the other skips it (claim-by-move enforced).

4. **Given** vault sync is active,
   **When** sync runs,
   **Then** `.env` files, tokens, WhatsApp sessions, and banking credentials are
   NEVER included in the synced payload — only markdown state files.

5. **Given** Odoo Community is deployed on the Cloud VM,
   **When** Cloud agent identifies an accounting action (draft invoice),
   **Then** Cloud writes a draft to Odoo via MCP (draft-only) and creates an
   approval file; Local approves and posts the final invoice/payment.

---

### Edge Cases

- **Duplicate ingestion**: Watcher processes the same email/message twice (should
  be idempotent — processed IDs tracked in memory or state file).
- **Vault lock conflict**: Two agents attempt to write to `Dashboard.md`
  simultaneously — single-writer rule (Local only) must prevent corruption.
- **Gmail API auth expiry**: OAuth token expires mid-operation — watcher must
  queue locally and alert human rather than crash silently.
- **WhatsApp session loss**: Playwright session is invalidated — watcher stops,
  writes error to `/Logs/`, alerts human without retrying indefinitely.
- **Banking API timeout**: System halts the payment flow and requires fresh
  human approval — never auto-retries payment actions.
- **Ralph Wiggum ceiling hit**: After 10 iterations task is still incomplete —
  Claude writes a partial completion log and escalates to human.
- **Approval file expiry**: Approval request older than 24h — system flags it
  as stale and moves to `/Rejected/` for human review.
- **Cloud VM unreachable**: Local agent continues normal operation; Cloud queue
  builds up and drains when VM recovers.
- **API rate limit hit**: Watcher applies exponential backoff, queues locally,
  writes `/Needs_Action/ALERT_rate_limit_*.md`, and auto-resumes — does NOT
  require human restart.

---

## Requirements *(mandatory)*

### Functional Requirements

**Perception Layer (Watchers)**

- **FR-001**: System MUST include a Gmail Watcher that polls for unread important
  emails every 120 seconds and writes structured `.md` files to `/Needs_Action/`.
- **FR-002**: System MUST include a WhatsApp Watcher (Playwright-based) that
  monitors for keyword-triggered messages (urgent, asap, invoice, payment, help)
  every 30 seconds and writes to `/Needs_Action/`.
- **FR-003**: System MUST include a File System Watcher that detects files
  dropped into a monitored folder and writes metadata `.md` files to `/Needs_Action/`.
- **FR-003a**: System MUST include a Finance Watcher that detects CSV bank
  statement files dropped into `/Accounting/`, parses transactions, and writes
  structured entries to `/Accounting/Current_Month.md` for use in the CEO Briefing.
- **FR-004**: All Watchers MUST be idempotent — duplicate events MUST NOT produce
  duplicate action files. Each watcher MUST persist processed IDs to
  `/State/<watcher_name>.json` in the vault so idempotency survives process
  restarts and crashes.
- **FR-004a**: When an API rate limit is encountered, Watchers MUST apply
  exponential backoff (1s → 2s → 4s … up to 60s cap), queue events locally,
  write an alert file to `/Needs_Action/ALERT_rate_limit_*.md`, and resume
  automatically — no human restart required.
- **FR-005**: All Watchers MUST be managed by a process manager (PM2 or custom
  Watchdog) that auto-restarts them on crash and persists across reboots.

**Vault & Memory**

- **FR-006**: System MUST use an Obsidian vault as the single source of truth
  with required folders: `/Needs_Action`, `/In_Progress`, `/Done`, `/Logs`,
  `/Plans`, `/Pending_Approval`, `/Approved`, `/Rejected`, `/Briefings`, `/State`.
- **FR-007**: System MUST maintain `Dashboard.md` (real-time summary),
  `Company_Handbook.md` (rules of engagement), and `Business_Goals.md`
  (targets and metrics) as core vault documents.
- **FR-008**: `Dashboard.md` MUST only be written by the Local agent (single-writer rule).

**Reasoning Layer**

- **FR-009**: Claude MUST read all relevant vault state before producing any plan
  or taking any action.
- **FR-010**: Claude MUST produce a structured `Plan.md` for every multi-step
  task with: Objective, Steps, Dependencies, Approval gates, Risk flags.
- **FR-011**: Claude MUST implement the Ralph Wiggum loop (Stop hook) for
  multi-step tasks — re-injecting the prompt until the task file moves to `/Done`
  or the max iteration ceiling (10) is reached.

**Action Layer (MCP)**

- **FR-012**: System MUST include a working email-mcp server for sending, drafting,
  and searching Gmail messages.
- **FR-013**: System MUST include a browser-mcp for web automation (payment
  portals, social media where API is unavailable).
- **FR-014**: System MUST include a calendar-mcp for scheduling pre-approved events.
- **FR-015** *(Gold+)*: System MUST include a custom Odoo MCP server using
  Odoo 19+ JSON-RPC API for accounting operations.

**Human-in-the-Loop (HITL)**

- **FR-016**: Claude MUST create a `/Pending_Approval/*.md` file for every
  sensitive action before executing it — no direct send/payment/deletion.
- **FR-017**: Approval MUST be triggered by the user physically moving the file
  to `/Approved/` — no verbal or in-chat approval is sufficient.
- **FR-018**: Approval files MUST expire after 24 hours; expired files MUST be
  moved to `/Rejected/` automatically.

**Observability & Alerts**

- **FR-019a**: On any critical failure (auth expiry, WhatsApp session loss, Ralph
  Wiggum ceiling hit, watcher crash not auto-recovered), the system MUST:
  (1) write a `/Needs_Action/ALERT_<type>_<timestamp>.md` file to the vault, AND
  (2) send an email alert to the owner's address via email-mcp.

**Security**

- **FR-019**: Credentials MUST NOT be stored in markdown or vault files — only
  environment variables and OS-native secret managers.
- **FR-020**: All action scripts MUST support a `DRY_RUN` mode that logs intended
  actions without executing them.
- **FR-021**: Audit logs MUST be written to `/Logs/YYYY-MM-DD.json` and retained
  for a minimum of 90 days.

**Business Audit**

- **FR-022**: System MUST generate a Monday Morning CEO Briefing every week with:
  Revenue vs Target, Completed Tasks, Bottleneck table, Cost-optimization
  suggestions, and Upcoming deadlines.
- **FR-023** *(Gold+)*: System MUST integrate LinkedIn, Facebook, Instagram, and
  Twitter/X using their official OAuth APIs (LinkedIn API, Facebook Graph API,
  Instagram Graph API, Twitter/X API v2) to post messages and pull engagement
  summaries for the CEO Briefing. When an API's free-tier limit is exceeded,
  the system MUST degrade gracefully: log the limitation, include a note in the
  briefing section, and continue without failing the full audit.

**Cloud/Local Separation** *(Platinum)*

- **FR-024**: Cloud agent MUST have draft-only authority — it MUST NOT send
  emails, WhatsApp messages, post to social, or execute payments.
- **FR-025**: Vault sync (Git or Syncthing) MUST exclude secrets, tokens,
  WhatsApp sessions, and banking credentials.
- **FR-026**: Claim-by-move rule MUST be enforced: first agent to move an item
  from `/Needs_Action/<domain>/` to `/In_Progress/<agent>/` owns it exclusively.

**Agent Skills**

- **FR-027**: ALL AI functionality MUST be implemented as Agent Skills (SKILL.md
  files in `.claude/`) so capabilities can be instantly onboarded to new instances.

### Key Entities

- **Action Item**: A structured `.md` file in `/Needs_Action/` representing a
  trigger event (email, WhatsApp message, file drop, finance alert) with
  frontmatter metadata (type, source, priority, status, timestamp).
- **Plan**: A `Plan.md` in `/Plans/` capturing Claude's reasoning: Objective,
  Steps, Dependencies, Approval gates, Risk flags, completion status.
- **Approval Request**: A `.md` file in `/Pending_Approval/` describing a
  sensitive action requiring human authorization before execution.
- **CEO Briefing**: A weekly report in `/Briefings/YYYY-MM-DD_Monday_Briefing.md`
  with structured sections covering revenue, tasks, bottlenecks, and suggestions.
- **Audit Log Entry**: A JSON record in `/Logs/YYYY-MM-DD.json` capturing every
  MCP action with timestamp, actor, target, approval status, and result.
- **Agent Skill**: A SKILL.md file in `.claude/` defining a reusable AI
  capability (e.g., email-triage, invoice-generator, ceo-briefing-generator).
- **Watcher State**: A `/State/<watcher_name>.json` file in the vault recording
  processed event IDs for each watcher, enabling idempotency across crashes and
  restarts.

---

## Success Criteria *(mandatory)*

### Measurable Outcomes

**Bronze**
- **SC-001**: A file dropped into the monitored folder appears as an action item
  in `/Needs_Action` within 60 seconds in 100% of test cases.
- **SC-002**: Claude successfully reads from and writes to the vault without
  manual intervention in ≥ 95% of triggered runs.
- **SC-003**: A crashed watcher process is restarted automatically within 60
  seconds without human intervention.

**Silver**
- **SC-004**: A new email classified as important appears as an action item in
  `/Needs_Action` within 3 minutes of arrival, in ≥ 90% of test cases.
- **SC-005**: 100% of actions that require external sends (email, social post)
  produce a `/Pending_Approval/` file before any execution occurs — zero
  unauthorized sends.
- **SC-006**: Once a user moves an approval file to `/Approved/`, the MCP
  executes the action and logs it within 2 minutes in ≥ 95% of cases.

**Gold**
- **SC-007**: The Monday CEO Briefing is generated within 10 minutes of the
  scheduled trigger in ≥ 99% of weekly runs, with all required sections
  populated.
- **SC-008**: At least one cost-optimization suggestion is identified and
  presented per weekly audit when subscription data is available.
- **SC-009**: The Ralph Wiggum loop completes multi-step tasks without premature
  exit in ≥ 99% of runs, up to the 10-iteration ceiling.
- **SC-010**: Audit logs capture 100% of MCP-executed actions with no missing
  entries for the 90-day retention window.

**Platinum**
- **SC-011**: With local machine offline, Cloud drafts a reply and writes an
  approval file within 5 minutes of an email arriving, in ≥ 95% of test cases.
- **SC-012**: No `.env` file, token, WhatsApp session, or banking credential
  ever appears in the vault sync payload — verified by automated scan.
- **SC-013**: When two agents detect the same `/Needs_Action` item, only one
  processes it — zero double-processing events in concurrent stress tests.
- **SC-014**: The system runs unattended for ≥ 24 hours on the Cloud VM with all
  watchers alive and logs continuously written.

## Clarifications

### Session 2026-02-22

- Q: How should the system handle API rate limits (Gmail, WhatsApp)? → A: Exponential backoff (1s→2s→4s…up to 60s) with local event queue; writes a human alert file to `/Needs_Action/ALERT_rate_limit_*.md`; resumes automatically without requiring human restart.
- Q: How should the system alert the user on critical failures (auth expiry, WA session loss, Ralph loop ceiling)? → A: Send an email to self via email-mcp AND write `/Needs_Action/ALERT_*.md` to vault.
- Q: Should Watcher processed IDs persist across restarts? → A: File-based — each watcher writes processed IDs to `/State/<watcher_name>.json` in the vault; survives crashes and restarts.
- Q: How should social media integrations (LinkedIn, Facebook, Instagram, Twitter/X) be implemented? → A: Official APIs with OAuth for all platforms (LinkedIn API, Facebook Graph API, Instagram Graph API, Twitter/X API v2); degrade gracefully when API tier limits are exceeded rather than failing hard.
- Q: What is the banking/finance data source for the Finance Watcher and CEO Briefing? → A: CSV file drop — user exports bank statement as CSV into `/Accounting/`; Finance Watcher parses it automatically. No live banking API required.

---

### Assumptions

- Obsidian vault is located at a fixed local path configured via `.env`.
- Gmail OAuth2 credentials are pre-provisioned by the user.
- WhatsApp Web session is pre-authenticated; session path is configured in `.env`.
- Banking/finance data is sourced from user-exported CSV bank statements dropped
  into `/Accounting/`. No live banking API integration is required; the Finance
  Watcher parses CSV files automatically.
- Odoo 19+ Community Edition is pre-installed for Gold/Platinum tiers.
- Cloud VM (Oracle/AWS) is provisioned by the user for Platinum tier.
- Git is used as the vault sync mechanism for Platinum (Syncthing is an
  alternative but not required).
- The Monday briefing scheduled trigger is managed via Windows Task Scheduler
  (local) and cron (Cloud VM).
