# Tasks: Digital FTE Agent

**Input**: Design documents from `/specs/001-digital-fte-agent/`
**Prerequisites**: plan.md ✅, spec.md ✅, research.md ✅, data-model.md ✅, contracts/ ✅, quickstart.md ✅

**Organization**: Tasks grouped by user story (Bronze → Silver → Gold → Platinum) to enable incremental hackathon delivery. Each tier is independently testable before advancing.

**Tests**: No automated test suite tasks (not explicitly requested). Acceptance tests from `quickstart.md` and SC-* success criteria serve as validation gates at each tier checkpoint.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no shared state)
- **[Story]**: US1=Bronze, US2=Silver, US3=Gold, US4=Platinum
- Paths use plan.md `src/` layout with UV Python project and Node.js MCP servers

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Obsidian installation, UV project initialization, vault template scaffolding, vault setup script, Node.js MCP skeletons, PM2 config, environment files

**⚠️ Obsidian Prerequisite**: Obsidian v1.10.6+ must be installed before vault files are useful. Install from https://obsidian.md/download, then use the vault setup script (T003a) to create `AI_Employee_Vault`.

- [X] T001 Initialize UV Python project with `uv init` and configure `pyproject.toml` with all Python dependencies: `google-api-python-client`, `google-auth-oauthlib`, `playwright`, `watchdog`, `python-dotenv`, `httpx`, `tweepy`, `facebook-sdk`, `pandas`, `pytest`, `fastmcp`
- [X] T002 Create `src/` package hierarchy with empty `__init__.py` files: `src/__init__.py`, `src/watchers/__init__.py`, `src/orchestrator/__init__.py`, `src/mcp_servers/__init__.py`, `src/audit/__init__.py`, `src/skills/__init__.py`
- [X] T003 [P] Create `vault_template/` directory tree with `.gitkeep` placeholders: `Needs_Action/`, `In_Progress/`, `Done/`, `Plans/`, `Pending_Approval/`, `Approved/`, `Rejected/`, `Logs/`, `State/`, `Accounting/`, `Briefings/`, `Invoices/`, `Updates/`
- [X] T003a Create `scripts/setup_vault.py`: reads `VAULT_PATH` from `.env`; copies all contents of `vault_template/` into `VAULT_PATH` (creating directory if not exists); skips `.gitkeep` files; prints instructions to open `VAULT_PATH` as an Obsidian vault; run once after setting `VAULT_PATH` in `.env` to initialize `AI_Employee_Vault`
- [X] T004 [P] Create `vault_template/Dashboard.md` with required schema: bank balance placeholder, pending messages count, active projects table, recent activity log section
- [X] T005 [P] Create `vault_template/Company_Handbook.md` with default rules of engagement: response SLAs, approval thresholds (`payment > $100 requires approval`), flagging rules for new contacts
- [X] T006 [P] Create `vault_template/Business_Goals.md` with Q1 template: revenue targets, key metrics table (client response time, invoice payment rate, software costs), active projects, subscription audit rules
- [X] T007 [P] Create `vault_template/Accounting/Current_Month.md` as blank transaction log template with markdown table header (date, description, amount, balance, category)
- [X] T008 [P] Create `.env.example` with all required environment variables: `VAULT_PATH`, `GMAIL_CLIENT_ID`, `GMAIL_CLIENT_SECRET`, `GMAIL_TOKEN_PATH`, `WHATSAPP_SESSION_PATH`, `BANK_CSV_DROP_PATH`, `ODOO_URL`, `ODOO_DB`, `ODOO_USERNAME`, `ODOO_API_KEY`, `LINKEDIN_ACCESS_TOKEN`, `TWITTER_BEARER_TOKEN`, `FACEBOOK_ACCESS_TOKEN`, `DRY_RUN=true`, `MAX_ITERATIONS=10`, `AGENT_MODE=local`, `CLOUD_AGENT_ID`
- [X] T009 [P] Create `.gitignore` covering: `.env`, `WhatsApp Session/`, `vault_template/State/*.json`, `vault_template/Logs/*.json`, `__pycache__/`, `.pytest_cache/`, `node_modules/`, `*.pyc`
- [X] T010 [P] Create `src/mcp_servers/email_mcp/package.json`, `src/mcp_servers/browser_mcp/package.json`, `src/mcp_servers/calendar_mcp/package.json` — each with MCP SDK dependency (`@modelcontextprotocol/sdk`) and `main` entry pointing to `index.js`
- [X] T011 [P] Create `pm2.config.js` at project root with process entries for all local watchers and services: `filesystem_watcher`, `gmail_watcher`, `whatsapp_watcher`, `finance_watcher`, `orchestrator`, `watchdog` — each with `interpreter: 'python3'`, restart policy, and log path
- [X] T012 [P] Create `.claude/settings.json` skeleton with MCP server registrations (email, browser, calendar, filesystem built-in) and empty hooks section for Stop hook registration in Phase 5
- [X] T013 [P] Create `.claude/` directory structure: `.claude/hooks/` (empty), `.claude/skills/` (empty) for Agent Skill SKILL.md files

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Core shared infrastructure — exceptions, retry, state management, audit logger, BaseWatcher ABC, vault utilities, DRY_RUN guard, orchestrator skeleton

**⚠️ CRITICAL**: No user story implementation can begin until this phase is complete

- [X] T014 Implement custom exception hierarchy in `src/exceptions.py`: `WatcherError` (base), `AuthExpiredError`, `RateLimitError`, `NetworkError`, `SessionInvalidError`, `ParseError`, `ConstitutionalBreachError` — all with `message`, `user_message`, `action_hint` fields; `to_markdown()` for Obsidian error cards
- [X] T015 [P] Implement `src/retry_handler.py` with `@with_retry(max_attempts=3, base_delay=1, max_delay=60)` decorator using exponential backoff; catch `NetworkError` and `RateLimitError` only; re-raise on max attempts exceeded; user-friendly log messages
- [X] T016 Implement `src/state_manager.py` with `load_state(watcher_name: str) -> dict` and `save_state(watcher_name: str, state: dict)`: atomic write via tmp-rename; graceful fallback to {} on missing/corrupt file; VAULT_PATH fallback warning
- [X] T017 [P] Implement `src/audit/audit_logger.py` with `log_action(...)` and `log_error(...)`: NDJSON append to `VAULT_PATH/Logs/YYYY-MM-DD.json`; stderr fallback if vault unavailable; 90-day retention note
- [X] T018 Implement `BaseWatcher` ABC in `src/watchers/base_watcher.py`: abstract `check_for_updates/create_action_file/get_event_id`; graceful error handling per category; atomic file writes; idempotency via state_manager; Obsidian error cards on auth/breach errors
- [X] T019 [P] Implement `src/vault_utils.py`: `move_file`, `update_dashboard` (lock+single-writer rule), `create_pending_approval`, `check_approved`, `claim_task` (atomic rename, returns False on race condition)
- [X] T020 [P] Implement `src/dry_run.py` with `is_dry_run() -> bool` (default true) and `dry_run_guard(action_name, payload)` returning True when active; logs friendly [DRY RUN] notice via audit_logger
- [X] T021 Implement `src/orchestrator/orchestrator.py`: `Orchestrator` class with `register_watcher`, `register_schedule`, `run()` loop with SIGINT/SIGTERM graceful shutdown, per-item error isolation, claim-by-move dispatch
- [X] T022 [P] Implement `src/orchestrator/watchdog.py`: PID-file-based process monitor; restarts crashed processes via `subprocess.Popen`; audit logs each restart; user-friendly log messages
- [X] T023 Write `tests/test_foundation.py` smoke tests: state roundtrip, corrupted-file fallback, retry backoff, auth no-retry, audit file write, vault unavailable fallback, claim_task atomic, create_pending_approval

**Checkpoint**: Foundation complete — all user story phases can now begin

---

## Phase 3: User Story 1 — Bronze Foundation (Priority: P1) 🎯 MVP

**Goal**: A working Obsidian-backed AI Employee that monitors a local drop folder, creates structured action items with YAML front-matter, and completes the full vault lifecycle (Needs_Action → claim → In_Progress → Pending_Approval → Approved → Done) with Dashboard updates and Agent Skills.

**Independent Test (SC-001, SC-002, SC-003)**:
1. Drop any `.md` file into the configured drop folder
2. Verify `VAULT_PATH/Needs_Action/FILE_<name>.md` appears within 60 seconds with correct YAML front-matter
3. Run the `vault-monitor` Agent Skill; verify `Plans/PLAN_<name>.md` created with approval gate
4. Move approval file from `Pending_Approval/` to `Approved/`
5. Verify artifact moves to `Done/` and Dashboard `## Recent Activity` is updated within 5 minutes

- [X] T024 [US1] Implement `src/watchers/filesystem_watcher.py` extending `BaseWatcher`: use `watchdog` `Observer` + `FileSystemEventHandler` on `BANK_CSV_DROP_PATH` (reuse pattern or separate `FILE_DROP_PATH` env var); override `check_for_updates()` to return queued file events; override `create_action_file(item)` to write `FILE_<source_name>.md` to `VAULT_PATH/Needs_Action/` with YAML front-matter (type=file_drop, original_name, size, received, priority=medium, status=pending); override `get_event_id(item)` as file path hash; persist processed paths in state via `state_manager`
- [X] T025 [US1] Implement `src/orchestrator/approval_handler.py`: `ApprovalHandler` class watching `VAULT_PATH/Approved/` using `watchdog`; on new file arrival, read YAML front-matter to identify `action` type and `plan_ref`; for Bronze tier (action=file_move), call `vault_utils.move_file()` to move artifact to `Done/`; call `audit_logger.log_action()`; call `vault_utils.update_dashboard()`; move the approval file itself to `Done/`
- [X] T026 [P] [US1] Extend `src/vault_utils.py` `update_dashboard()` to handle the single-writer rule: check `AGENT_MODE` env var; if `cloud`, write update entry to `VAULT_PATH/Updates/dashboard_update_<timestamp>.md` instead of writing directly; if `local`, acquire/release `.dashboard.lock` file with 5-second timeout before writing
- [X] T027 [US1] Register `FilesystemWatcher` and `ApprovalHandler` in `src/orchestrator/orchestrator.py`: instantiate both from env vars; add filesystem watcher to orchestrator's watcher list; start approval handler in separate thread; add `watchdog` (process monitor) to startup sequence
- [X] T028 [P] [US1] Create Agent Skill `.claude/skills/vault-monitor.md`: skill reads all files in `/Needs_Action/`; for each, applies claim via `claim_task()`; creates `Plans/PLAN_<name>.md` with Objective, Steps, Dependencies, Approval gates, Risk flags; writes `Pending_Approval/<action>_<name>_<date>.md` for sensitive actions; moves item to `/In_Progress/claude/`
- [X] T029 [P] [US1] Create Agent Skill `.claude/skills/approval-handler.md`: skill reads `/Approved/` folder; matches approval file to its Plan via `plan_ref` field; calls appropriate action (file move, MCP call); logs result via audit_logger; moves plan + approval + source files to `/Done/`; updates Dashboard
- [X] T030 [US1] Update `pm2.config.js` with final `filesystem_watcher` and `orchestrator` entries: set `script` to `src/watchers/filesystem_watcher.py` and `src/orchestrator/orchestrator.py`, `interpreter: 'python3'`, `restart_delay: 3000`, `log_file: 'logs/filesystem_watcher.log'`
- [X] T031 [US1] Run SC-001 acceptance test per `quickstart.md` step 10: drop a `.md` test file into configured drop folder; verify `Needs_Action/FILE_*.md` created with correct YAML within 60 seconds; print PASS/FAIL → `tests/test_bronze_acceptance.py` (SC001 class)
- [X] T032 [US1] Run SC-002/SC-003 acceptance tests: run `vault-monitor` skill manually (`claude --skill vault-monitor`); verify Plan.md created and Pending_Approval file created; move to Approved; verify Done/ and Dashboard updated within 5 minutes; print PASS/FAIL → `tests/test_bronze_acceptance.py` (SC002/SC003 class)

**Checkpoint**: Bronze tier complete — Filesystem Watcher, HITL approval cycle, vault lifecycle, Dashboard updates all functional

---

## Phase 4: User Story 2 — Silver Functional Assistant (Priority: P2)

**Goal**: Add Gmail, WhatsApp, and Finance watchers; deploy email-mcp for email send/draft; implement HITL for email actions; add scheduling; create LinkedIn posting and invoice generation Agent Skills — making the AI Employee a true multi-channel functional assistant.

**Independent Test (SC-004, SC-005, SC-006)**:
1. Send test email to monitored Gmail → verify `Needs_Action/EMAIL_*.md` within 3 minutes
2. Send WhatsApp message with keyword "invoice" → verify `Needs_Action/WHATSAPP_*.md` within 90 seconds
3. Drop bank CSV into `BANK_CSV_DROP_PATH` → verify `Accounting/Current_Month.md` updated within 5 minutes

- [X] T033 [US2] Implement `src/watchers/gmail_watcher.py` extending `BaseWatcher`: use `google-api-python-client` with OAuth2 credentials loaded from `GMAIL_TOKEN_PATH`; override `check_for_updates()` using `users.messages.list(q='is:unread is:important')` with 120-second interval; on new messages, fetch full message via `users.messages.get()`; extract headers (From, Subject, Date); override `create_action_file()` to write `EMAIL_<id>.md` with YAML front-matter (type=email, from, subject, received, priority=high, status=pending) and `## Email Content` body with snippet; override `get_event_id()` returning Gmail message ID; persist processed IDs in `/State/gmail_watcher.json`
- [X] T034 [P] [US2] Create OAuth2 setup script `scripts/setup_gmail_auth.py`: run `InstalledAppFlow` with scopes `['gmail.readonly']`; save token to `GMAIL_TOKEN_PATH`; print instructions for first-time use including how to enable Gmail API in Google Cloud Console
- [X] T035 [US2] Implement `src/watchers/whatsapp_watcher.py` extending `BaseWatcher`: use `playwright` `sync_playwright()` with `chromium.launch_persistent_context(WHATSAPP_SESSION_PATH, headless=True)`; navigate to `https://web.whatsapp.com`; wait for `[data-testid="chat-list"]`; query `[aria-label*="unread"]` elements; filter chats containing priority keywords (`['urgent','asap','invoice','payment','help','pricing']`); extract sender and text; override `create_action_file()` to write `WHATSAPP_<hash>.md` with YAML front-matter (type=whatsapp, from, keyword, received, priority=high, status=pending); check interval 30s; raise `SessionInvalidError` if chat-list times out after 30s; persist processed chat hashes in `/State/whatsapp_watcher.json`
- [X] T036 [P] [US2] Implement `src/watchers/finance_watcher.py` extending `BaseWatcher`: watch `BANK_CSV_DROP_PATH` for new CSV files using `watchdog`; on new file, use `pandas.read_csv()` to parse transactions (columns: date, description, amount, balance); append each row as markdown table row to `VAULT_PATH/Accounting/Current_Month.md`; call `audit_logic.analyze_transaction()` on each row and flag subscription matches to `Needs_Action/SUBSCRIPTION_*.md`; persist processed filenames in `/State/finance_watcher.json`
- [X] T037 [US2] Implement `src/mcp_servers/email_mcp/index.js` as Node.js MCP server: export tools `email_send(to, subject, body, attachment?)`, `email_draft(to, subject, body)`, `email_search(query, max_results?)`; use `nodemailer` or Gmail API Node client; read credentials from env vars; implement `DRY_RUN` check (log intent if true); implement error types: `AUTH_EXPIRED`, `QUOTA_EXCEEDED`, `APPROVAL_MISSING` (block send if `AGENT_MODE=cloud`); register in `.claude/settings.json` under `mcpServers.email`
- [X] T038 [P] [US2] Implement `src/mcp_servers/calendar_mcp/index.js` as Node.js MCP server: export tools `calendar_create_event(summary, start, end, description?)`, `calendar_list_events(time_min, time_max)`; use Google Calendar API Node client; DRY_RUN support; register in `.claude/settings.json` under `mcpServers.calendar`
- [X] T039 [US2] Implement HITL email integration in `src/orchestrator/approval_handler.py`: add handler for `action=send_email` approval type; on approval file detected in `/Approved/`, read `to`, `subject`, `body`, `attachment` from approval YAML front-matter; call Gmail API via `google-api-python-client`; log result; move approval + plan + source files to `/Done/`; update Dashboard
- [X] T040 [P] [US2] Implement `src/audit/audit_logic.py` with `SUBSCRIPTION_PATTERNS: dict[str, str]` (domain → vendor name for netflix, spotify, adobe, notion, slack, github, figma, zoom); `analyze_transaction(transaction: dict) -> dict | None` returning `{type: 'subscription', name, amount, date}` for matches; `run_subscription_audit(vault_path: Path) -> list[dict]` reading `Accounting/Current_Month.md`, running analyze on each row, grouping by vendor, flagging vendors with no Done/ task mentions in 30 days
- [X] T041 [US2] Register all four watchers (`FilesystemWatcher`, `GmailWatcher`, `WhatsAppWatcher`, `FinanceWatcher`) in `src/orchestrator/main.py`: instantiate each from env vars; register conditionally when required env var is set; log skip message when env var missing
- [X] T042 [P] [US2] Update `pm2.config.js` with entries for `gmail_watcher`, `whatsapp_watcher`, `finance_watcher`: each with `script`, `interpreter: 'python3'`, `restart_delay: 5000`, dedicated `log_file` path
- [X] T043 [P] [US2] Create Agent Skill `.claude/skills/email-triage.md`: reads `EMAIL_*.md` action items from Needs_Action; categorizes by sender (known/unknown from Company_Handbook contacts list); drafts reply using email content; for known contacts creates approval with `action=send_email`; for unknown creates approval with higher escalation flag; logs triage decision
- [X] T044 [P] [US2] Create Agent Skill `.claude/skills/invoice-generator.md`: triggered by WHATSAPP action item containing "invoice" keyword; reads `/Accounting/Rates.md` for client rates; generates invoice markdown to `VAULT_PATH/Invoices/YYYY-MM_<client>.md`; creates approval file `Pending_Approval/EMAIL_invoice_<client>_<date>.md` for email send via email-mcp
- [X] T045 [US2] Implement LinkedIn posting in `src/skills/linkedin_poster.py`: use `httpx` to POST to `https://api.linkedin.com/v2/ugcPosts` with `LINKEDIN_ACCESS_TOKEN`; DRY_RUN guard from `src/dry_run.py`; construct post payload from `Business_Goals.md` weekly highlight; log result via `audit_logger`
- [X] T046 [US2] Wire LinkedIn poster to orchestrator Monday 09:00 weekly schedule in `src/orchestrator/main.py`; add `_post_linkedin_weekly()` closure to register_schedule (7-day interval); guard with DRY_RUN check; skipped gracefully if LINKEDIN_ACCESS_TOKEN not set
- [X] T047 [US2] Create SC-004 acceptance test `tests/test_silver_acceptance.py` (SC004GmailTest): polls Needs_Action/ for EMAIL_*.md after new important Gmail message; validates type/from/subject/status/priority fields; 3-minute timeout; skipped when GMAIL_TOKEN_PATH not set
- [X] T048 [US2] Create SC-005 acceptance test `tests/test_silver_acceptance.py` (SC005WhatsAppTest): polls Needs_Action/ for WHATSAPP_*.md after keyword message; validates type/chat/keywords_matched/status fields; 90-second timeout; skipped when WHATSAPP_SESSION_PATH not set

**Checkpoint**: Silver tier complete — all 4 Watchers running, email-mcp operational, HITL for email, LinkedIn posting scheduled, invoice-generator skill active

---

## Phase 5: User Story 3 — Gold Autonomous Employee (Priority: P3)

**Goal**: Full cross-domain integration — Odoo ERP accounting, Facebook/Instagram/Twitter social, Ralph Wiggum persistence loop, browser-mcp for payment portals, weekly CEO Briefing with subscription audit, comprehensive audit logging, and graceful error degradation.

**Independent Test (SC-007, SC-008, SC-009, SC-010)**:
1. Trigger CEO Briefing via orchestrator; verify `/Briefings/YYYY-MM-DD_Monday_Briefing.md` contains all sections (Revenue, Bottlenecks, Cost Optimization) within 10 minutes
2. Create Odoo draft invoice via `odoo-mcp` in DRY_RUN=false; verify draft (not posted) in Odoo dashboard
3. Start Ralph Wiggum loop with task not in /Done; verify re-injection fires; move task to /Done; verify loop exits
4. Perform 3 MCP actions; verify all 3 appear as JSON entries in `Logs/YYYY-MM-DD.json`

- [X] T049 [US3] Implement Ralph Wiggum Stop hook in `.claude/hooks/stop.py`: read `VAULT_PATH/In_Progress/claude/` for any active task state file; if task file found and corresponding done file NOT in `VAULT_PATH/Done/`, read original prompt from state file, re-inject prompt and block exit (return non-zero exit code to Claude Code); increment iteration counter in state file; allow exit when counter exceeds `MAX_ITERATIONS` env var (default 10) or task found in `/Done/`; log each iteration to `audit_logger`
- [X] T050 [P] [US3] Register Stop hook in `.claude/settings.json` under `hooks.stop`: point to `.claude/hooks/stop.py` with `interpreter: 'python3'`
- [X] T051 [US3] Implement `src/audit/ceo_briefing.py` with `generate_briefing(vault_path: Path, period_start: date, period_end: date) -> Path`: read `Business_Goals.md` for revenue target and metrics; parse `Accounting/Current_Month.md` transaction table with pandas for period revenue; scan `Done/` for completed task files in period; call `run_subscription_audit()` from `audit_logic.py`; compute bottlenecks (tasks with `created` to `done` delta > target); write briefing to `VAULT_PATH/Briefings/YYYY-MM-DD_Monday_Briefing.md` per data-model.md CEO Briefing schema (Executive Summary, Revenue, Completed Tasks, Bottlenecks, Proactive Suggestions, Cost Optimization)
- [X] T052 [P] [US3] Wire CEO Briefing to orchestrator Sunday 22:00 schedule in `src/orchestrator/orchestrator.py`: compute `period_start` (7 days ago) and `period_end` (today); call `generate_briefing()`; call `update_dashboard()` with briefing link in Recent Activity
- [X] T053 [P] [US3] Create Agent Skill `.claude/skills/ceo-briefing.md`: reads `Business_Goals.md`, `Done/` tasks from last 7 days, `Accounting/Current_Month.md`; synthesizes Executive Summary paragraph; invokes `generate_briefing()` via vault file convention; updates Dashboard with briefing link and revenue status
- [X] T054 [US3] Implement `src/mcp_servers/odoo_mcp/server.py` as Python FastMCP server: tool `odoo_search_read(model, domain, fields, limit?)` — POST to `ODOO_URL/web/dataset/call_kw` with `method='search_read'`; tool `odoo_create_draft(model, values)` — create record (always in draft/unposted state, DRY_RUN guard logs intent only when DRY_RUN=true); tool `odoo_post_record(model, record_id, approval_token)` — validate `approval_token` against `VAULT_PATH/Approved/` file before posting (HITL gate, raise `APPROVAL_MISSING` if no matching approval); authenticate via JSON-RPC using `ODOO_USERNAME` + `ODOO_API_KEY`; run with `uv run python -m src.mcp_servers.odoo_mcp.server`
- [X] T055 [P] [US3] Create `src/mcp_servers/odoo_mcp/__init__.py` exporting `server` entry point; create `src/mcp_servers/odoo_mcp/pyproject.toml` if needed for standalone execution; register in `.claude/settings.json` under `mcpServers.odoo`
- [X] T056 [US3] Implement `src/mcp_servers/browser_mcp/index.js` as Node.js MCP server: tool `browser_navigate(url)`, `browser_click(selector, approval_token?)`, `browser_fill(selector, value, approval_token?)` using Playwright headless Chromium; `browser_click` and `browser_fill` on payment-domain URLs require non-null `approval_token` validated against `VAULT_PATH/Approved/`; DRY_RUN support (log target action without executing click/fill); register in `.claude/settings.json` under `mcpServers.browser`
- [X] T057 [P] [US3] Implement `src/skills/facebook_poster.py`: use `httpx` to POST to `https://graph.facebook.com/v19.0/me/feed` with `FACEBOOK_ACCESS_TOKEN`; compose message from `Business_Goals.md` weekly highlight; DRY_RUN guard; log to `audit_logger` with `action_type='social_post'`, `target='facebook'`; return post ID or error
- [X] T058 [P] [US3] Implement `src/skills/instagram_poster.py`: two-step Graph API flow — POST to `/me/media` (create container) then `/me/media_publish` (publish); use `FACEBOOK_ACCESS_TOKEN`; DRY_RUN guard; log to `audit_logger` with `target='instagram'`
- [X] T059 [P] [US3] Implement `src/skills/twitter_poster.py`: use `tweepy.Client(bearer_token=TWITTER_BEARER_TOKEN)` with `create_tweet(text=message)`; rate-limit awareness (50 requests/month on free tier — log usage count in `/State/twitter_state.json`); DRY_RUN guard; log to `audit_logger` with `target='twitter'`
- [X] T060 [US3] Wire social posters to orchestrator Monday 09:30 schedule in `src/orchestrator/orchestrator.py`: run `facebook_poster`, `instagram_poster`, `twitter_poster` sequentially; catch per-platform errors (do not abort other platforms on single failure); log all results to `audit_logger`
- [X] T061 [US3] Wire subscription audit to CEO Briefing: call `run_subscription_audit(vault_path)` from `ceo_briefing.py` before generating briefing; write flagged subscriptions to `VAULT_PATH/Pending_Approval/SUBSCRIPTION_<vendor>_<date>.md`; include flagged items in briefing `## Cost Optimization` section with `[ACTION]` move-to-Approved cue
- [X] T062 [US3] Implement error degradation handlers in `src/orchestrator/orchestrator.py`: `handle_gmail_down()` — queue pending email drafts to `VAULT_PATH/Plans/queued/gmail_queue_<ts>.md`; `handle_banking_timeout()` — write `VAULT_PATH/Needs_Action/ALERT_banking_timeout_<ts>.md` and halt payment-related processing until re-approval; `handle_vault_locked()` — write to `/tmp/vault_fallback_<ts>.md` and retry sync every 60 seconds
- [X] T063 [US3] Add `odoo_mcp` entry to `pm2.config.js` with `interpreter: 'python3'`, `script: 'src/mcp_servers/odoo_mcp/server.py'`; install Node.js dependencies for browser_mcp with `npm install` step in setup
- [X] T064 [US3] Run SC-007 acceptance test: trigger `generate_briefing()` manually from orchestrator with current date; verify `/Briefings/*.md` created with all required sections (Executive Summary, Revenue, Completed Tasks, Bottlenecks, Proactive Suggestions) within 10 minutes; print PASS/FAIL
- [X] T065 [US3] Run SC-008/SC-009 acceptance tests: start Ralph Wiggum stop hook; create task state file in `/In_Progress/claude/`; verify hook fires on exit attempt; move task to `/Done/`; verify hook allows exit; log iteration count; print PASS/FAIL

**Checkpoint**: Gold tier complete — CEO Briefing, Odoo MCP, social APIs, Ralph Wiggum loop, browser-mcp, comprehensive audit logging, error degradation all functional

---

## Phase 6: User Story 4 — Platinum Always-On Cloud + Local Executive (Priority: P4)

**Goal**: Deploy Cloud agent on Oracle/AWS VM running 24/7 with Git vault sync; enforce Cloud (draft-only) vs Local (approval authority) agent separation; implement claim-by-move multi-agent coordination; validate the Platinum minimum passing gate: email arrives while Local is offline → Cloud drafts + writes approval → Local approves → MCP sends → Done.

**Independent Test (SC-011, SC-012, SC-013, SC-014)**:
1. Email arrives while local offline → Cloud creates draft + `Pending_Approval/email/*.md` → Local returns + user approves → Local email-mcp sends → task in Done/ + audit log entry ✅
2. Simultaneous task drop from Cloud and Local perspectives → only one agent claims via claim-by-move → other skips gracefully ✅
3. Cloud agent attempts payment action → `ConstitutionalBreachError` raised → action blocked ✅
4. Vault sync executes → `.env`, `State/*.json`, WhatsApp session excluded → markdown files synced ✅

- [X] T066 [US4] Create `pm2.cloud.config.js` at project root for Cloud VM: include only `gmail_watcher`, `finance_watcher`, `orchestrator` (cloud-mode), `watchdog` — explicitly exclude `whatsapp_watcher`; add `env: { AGENT_MODE: 'cloud' }` to all entries
- [X] T067 [P] [US4] Implement `src/orchestrator/cloud_constraints.py`: `assert_draft_only(action_type: str)` — raise `ConstitutionalBreachError` if `action_type in ('send_email','send_payment','execute_payment')`; `assert_no_payment_credentials()` — raise `ConstitutionalBreachError` if `BANK_API_TOKEN` env var is set; `assert_no_whatsapp_session()` — raise `ConstitutionalBreachError` if `WHATSAPP_SESSION_PATH` env var is set and path exists; called by orchestrator at startup when `AGENT_MODE=cloud`
- [X] T068 [US4] Modify `src/orchestrator/orchestrator.py` to support `AGENT_MODE`: at startup, read `AGENT_MODE` env var; if `cloud`, import and call all three `cloud_constraints.py` assertions; when processing tasks in cloud mode, redirect all `send_*` actions to write `VAULT_PATH/Pending_Approval/<domain>/` files instead of calling MCP; when in `local` mode, also process `/Pending_Approval/` queue by delegating to `approval_handler.py`
- [X] T069 [US4] Update `src/mcp_servers/email_mcp/index.js` to enforce `AGENT_MODE=cloud` restriction: if `process.env.AGENT_MODE === 'cloud'`, `email_send()` returns `{error: 'APPROVAL_MISSING', message: 'Cloud agent cannot send directly; write approval file to vault'}` without executing; `email_draft()` proceeds normally regardless of mode
- [X] T070 [P] [US4] Implement Git vault sync: create `vault_template/.gitignore` (exclude `.env`, `State/*.json`, `WhatsApp Session/`, `*.pyc`); create `scripts/sync_vault.sh` with `git -C $VAULT_PATH pull && git -C $VAULT_PATH add -A && git -C $VAULT_PATH commit -m "vault sync $(date -u +%Y-%m-%dT%H:%M:%SZ)" && git -C $VAULT_PATH push`; add vault sync to orchestrator schedule at 15-minute intervals; handle `git pull` conflicts by preferring remote (Cloud is drafter, Local is authority)
- [X] T071 [US4] Verify `claim_task()` in `src/vault_utils.py` handles concurrent access correctly: use `os.rename()` which is atomic on POSIX and NTFS; add `agent_id` to destination path (`In_Progress/<agent_id>/task.md`) so multiple agents have separate in-progress namespaces; return `False` on `FileNotFoundError` (already claimed)
- [X] T072 [P] [US4] Implement Dashboard single-writer enforcement in `src/vault_utils.py`: `acquire_dashboard_lock(vault_path) -> bool` creates `.dashboard.lock` file with agent_id + expiry timestamp; returns `False` if lock exists and not expired (5-second TTL); `release_dashboard_lock(vault_path)` removes lock file; Cloud agent `update_dashboard()` writes to `VAULT_PATH/Updates/dashboard_update_<ts>.md` instead when lock unavailable
- [X] T073 [US4] Implement Cloud update merge in Local orchestrator: add periodic task (every sync cycle) to read all files in `VAULT_PATH/Updates/`; apply each dashboard update entry to `Dashboard.md` via `update_dashboard()` with lock; move processed update files to `/Done/`
- [X] T074 [P] [US4] Create `scripts/setup_odoo_cloud.sh`: Docker Compose file (`docker-compose.odoo.yml`) with `odoo:19.0`, `postgres:15`, nginx reverse proxy; SSL setup instructions using Let's Encrypt certbot; health check endpoint at `/web/health`; backup cron job; instructions for pointing Cloud agent's `ODOO_URL` to the VM's public IP/domain
- [X] T075 [P] [US4] Create `scripts/setup_cloud_agent.sh`: automates Cloud VM bootstrap — install UV, Python 3.13, Node.js v24, PM2, Playwright headless deps (`apt-get install -y xvfb` for WhatsApp if needed), clone repo, copy `.env.cloud.example` to `.env`, run `uv sync`, run `npm install` in each MCP server dir, run `pm2 start pm2.cloud.config.js && pm2 save && pm2 startup`
- [X] T076 [P] [US4] Create `.env.cloud.example` with Cloud VM specific vars: `AGENT_MODE=cloud`, `CLOUD_AGENT_ID=cloud-01`, `VAULT_GIT_REMOTE=git@github.com:<user>/ai-employee-vault.git`, `VAULT_SYNC_INTERVAL_MINUTES=15`, `GMAIL_CLIENT_ID`, `GMAIL_CLIENT_SECRET`, `GMAIL_TOKEN_PATH`, `ODOO_URL`, `ODOO_DB`, `ODOO_USERNAME`, `ODOO_API_KEY`, `DRY_RUN=true` — exclude `WHATSAPP_SESSION_PATH` and `BANK_API_TOKEN`
- [X] T077 [US4] Implement Platinum acceptance test script `scripts/test_platinum_gate.py`: automated end-to-end simulation of the Platinum demo gate: (1) simulate email arrival to Needs_Action while `AGENT_MODE=cloud`, (2) verify Cloud creates draft + `Pending_Approval/email/*.md`, (3) simulate user approval (move file to Approved/), (4) switch to `AGENT_MODE=local`, verify Local's approval_handler calls email_mcp.email_send(), (5) verify Done/ file + audit log entry + Dashboard update; print SC-011 through SC-014 PASS/FAIL table
- [X] T078 [US4] Run `scripts/test_platinum_gate.py` locally with `DRY_RUN=true`; verify all 4 Platinum SCs PASS; write results to `VAULT_PATH/Logs/platinum_acceptance_YYYY-MM-DD.json`
- [X] T079 [US4] Run SC-012 claim-by-move race test: create identical task file in `Needs_Action/`; start two orchestrator instances simultaneously with different `CLOUD_AGENT_ID`; verify only one claims the task; verify other logs "task already claimed, skipping"; print PASS/FAIL
- [X] T080 [US4] Run SC-013 cloud constraint test: set `AGENT_MODE=cloud` and `BANK_API_TOKEN=dummy`; start orchestrator; verify `ConstitutionalBreachError` raised at startup by `assert_no_payment_credentials()`; verify orchestrator halts with clear error message; print PASS/FAIL
- [X] T081 [US4] Run SC-014 vault sync security test: run `scripts/sync_vault.sh` with test vault; inspect `git status` and `git log`; verify `.env` excluded; verify `State/*.json` excluded; verify `WhatsApp Session/` excluded; verify `Dashboard.md` synced; print PASS/FAIL

**Checkpoint**: Platinum tier complete — Cloud/Local dual-agent separation, Git vault sync, claim-by-move, single-writer Dashboard, Platinum gate PASS

---

## Phase 7: Polish & Cross-Cutting Concerns

**Purpose**: Final hardening, documentation, security audit, demo prep, submission checklist

- [X] T082 [P] Update `README.md` with: architecture diagram (ASCII from spec), Bronze→Silver→Gold→Platinum tier descriptions, step-by-step setup referencing `quickstart.md`, security disclosure section (DRY_RUN default, HITL safeguards, credential handling via env vars, no secrets in vault), tier declaration (Platinum), demo video link placeholder
- [X] T083 [P] Security audit pass: verify `.env` absent from git history (`git log --all --full-history -- .env`); verify `State/*.json` excluded from vault sync; verify all MCP tools default to DRY_RUN=true; verify `cloud_constraints.py` blocks payment credentials in cloud env; verify WhatsApp session never synced
- [X] T084 [P] Run `uv run pytest tests/test_foundation.py` and all acceptance test scripts; capture output; fix any failures before submitting
- [X] T085 [P] Run `quickstart.md` step 12 Platinum acceptance gate end-to-end as demo rehearsal — requires PM2 watchers running + real credentials; record 5–10 min demo video: filesystem drop → Gmail action → HITL approval → CEO Briefing → Odoo draft → Cloud-Local gate; record 5–10 minute demo video covering all tier highlights
- [X] T086 Tag git release `v1.0.0-platinum`; push to GitHub repository; verify README.md renders correctly with setup instructions and architecture diagram

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies — start immediately
- **Foundational (Phase 2)**: Depends on Phase 1 — **BLOCKS all user story phases**
- **US1 Bronze (Phase 3)**: Depends on Phase 2
- **US2 Silver (Phase 4)**: Depends on Phase 2; shares vault infrastructure with US1 but can be worked in parallel with US1 by a second developer
- **US3 Gold (Phase 5)**: Depends on Phase 2 complete + Phase 3 vault lifecycle running + Phase 4 watchers operational
- **US4 Platinum (Phase 6)**: Depends on all prior phases complete (all MCP servers deployed, all watchers running, audit logging functional)
- **Polish (Phase 7)**: After all desired user stories complete

### User Story Dependencies

| Story | Hard Depends On | Can Start After |
|-------|----------------|-----------------|
| US1 Bronze | Phase 2 complete | Phase 2 checkpoint |
| US2 Silver | Phase 2 complete | Phase 2 checkpoint (parallel with US1) |
| US3 Gold | US1 vault lifecycle + US2 watchers + Phase 2 | US2 checkpoint |
| US4 Platinum | All prior phases + all MCP servers registered | US3 checkpoint |

### Within Each User Story (execution order)

1. Watcher implementation → orchestrator registration → PM2 config
2. MCP server implementation → HITL integration → approval handler update
3. Agent Skills → schedule wiring
4. Acceptance test runs last

### Parallel Opportunities

- All Phase 1 [P] tasks (T003–T013): run simultaneously
- Phase 2 [P] tasks (T015, T017, T019, T020, T022): run after T014/T016/T018
- US2: Gmail watcher (T033–T034), WhatsApp watcher (T035), Finance watcher (T036) are independent — build in parallel
- US2: email-mcp (T037) and calendar-mcp (T038) are independent — build in parallel
- US3: Social posters FB (T057), IG (T058), Twitter (T059) are fully independent
- US4: Cloud constraints (T067–T068), Git sync (T070), Dashboard lock (T072) are independent

---

## Parallel Example: Phase 2 Foundational

```bash
# Stream 1 (sequential — state/base must be built in order):
T014 (exceptions) → T016 (state_manager) → T018 (BaseWatcher) → T023 (smoke test)

# Stream 2 (parallel once T014 done):
T015 (retry_handler), T017 (audit_logger), T019 (vault_utils), T020 (dry_run), T022 (watchdog)
```

## Parallel Example: User Story 2 Silver

```bash
# Stream 1 (Gmail):
T033 → T034

# Stream 2 (WhatsApp - independent):
T035

# Stream 3 (Finance + Audit Logic):
T036 → T040

# Stream 4 (MCP servers - independent of watchers):
T037, T038

# Stream 5 (HITL + Skills - after T037 ready):
T039, T043, T044
```

---

## Implementation Strategy

### MVP First — Bronze Only (Phases 1–3)

1. Complete Phase 1: Setup (UV project, vault template, .env.example)
2. Complete Phase 2: Foundational (BaseWatcher, state, retry, vault utils, audit logger)
3. Complete Phase 3: US1 Bronze (Filesystem Watcher + HITL + vault lifecycle + Dashboard)
4. **STOP and VALIDATE**: Run SC-001/SC-002/SC-003 acceptance tests
5. Submit Bronze tier if time-constrained — this alone demonstrates core architecture

### Incremental Delivery (Recommended for Hackathon)

| Phase | Deliverable | Validates | Time Est. |
|-------|-------------|-----------|-----------|
| 1+2 | Foundation | Smoke tests pass | 3–4h |
| 3 | Bronze MVP | SC-001, SC-002, SC-003 | 4–6h |
| 4 | Silver | SC-004, SC-005, SC-006 | 8–10h |
| 5 | Gold | SC-007, SC-008, SC-009, SC-010 | 12–16h |
| 6 | Platinum | SC-011–SC-014 | 8–10h |
| 7 | Polish | Demo video, README | 2–3h |

### Hackathon Judging Priority

Given judging weights (Functionality 30%, Innovation 25%, Practicality 20%, Security 15%, Docs 10%):

1. **Bronze + Silver** — delivers most functionality quickly (30% weight)
2. **CEO Briefing (US3 T051)** — highest innovation signal (25% weight)
3. **DRY_RUN + HITL + audit logs** — visible in demo, covers security (15% weight)
4. **README + architecture diagram** — documentation (10% weight)
5. **Platinum** — only if Bronze–Gold complete with time remaining

---

## Notes

- [P] marker = different files, no shared state — safe to work simultaneously
- [USn] label maps each task to hackathon tier for traceability to spec.md
- `DRY_RUN=true` by default in `.env.example`; set `DRY_RUN=false` only after thorough demo testing
- WhatsApp Playwright requires `headless=False` on first run for QR code scan; use Xvfb on Linux Cloud VM
- Twitter API free tier: 50 requests/month — implement usage counter in `/State/twitter_state.json` to avoid quota exhaustion
- Claim-by-move atomicity: `os.rename()` is atomic on POSIX filesystems and NTFS; test on Windows Git Bash before Cloud deployment
- PM2 must be running for all acceptance tests requiring background watchers; use `pm2 status` to verify before running SC-* tests
- Commit after each tier checkpoint: `feat: bronze tier - filesystem watcher + HITL + vault lifecycle`
- Never commit `.env`, `State/*.json`, or WhatsApp session data to git
