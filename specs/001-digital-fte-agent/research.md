# Research: Digital FTE Agent — Phase 0 Findings

**Branch**: `001-digital-fte-agent` | **Date**: 2026-02-22
**Status**: Complete — all NEEDS CLARIFICATION resolved

---

## Decision 1: Process Management (Watcher Persistence)

**Decision**: PM2 (Node.js-based) as primary process manager for all Python Watchers

**Rationale**:
- Cross-platform (Windows 10 + Linux VM) — single config file `pm2.config.js`
- Built-in log capture (`pm2 logs`) with rotation — critical for silent failure debugging
- Auto-restart on crash with configurable restart delay and max-restarts limit
- Startup persistence via `pm2 startup` + `pm2 save` (survives reboots)
- Can run Python scripts: `pm2 start watcher.py --interpreter python3`
- On Windows, use `pm2 startup` with Task Scheduler integration

**Configuration pattern**:
```js
// pm2.config.js
module.exports = {
  apps: [
    { name: "gmail-watcher", script: "src/watchers/gmail_watcher.py",
      interpreter: "python3", restart_delay: 3000, max_restarts: 10 },
    { name: "whatsapp-watcher", script: "src/watchers/whatsapp_watcher.py",
      interpreter: "python3", restart_delay: 5000, max_restarts: 5 },
    { name: "filesystem-watcher", script: "src/watchers/filesystem_watcher.py",
      interpreter: "python3", restart_delay: 1000, max_restarts: 20 },
    { name: "finance-watcher", script: "src/watchers/finance_watcher.py",
      interpreter: "python3", restart_delay: 2000, max_restarts: 10 }
  ]
};
```

**Alternatives considered**:
- `supervisord` — Linux-only, not suitable for Windows local agent
- Custom `watchdog_process.py` — fragile, lacks log rotation, restarts are not OS-persisted
- Windows Task Scheduler only — no Unix equivalent for Cloud VM; inconsistent cross-platform

---

## Decision 2: Ralph Wiggum Stop Hook Pattern

**Decision**: Claude Code Stop hook that intercepts exit, checks `/Done` folder, re-injects prompt

**How it works**:
1. Orchestrator creates a state file: `/State/ralph_task_<id>.json` with the original prompt
2. Claude works on the multi-step task
3. On exit attempt, Stop hook fires (configured in `.claude/settings.json`)
4. Hook checks: Has the task file moved to `/Done`?
   - YES → allow exit (task complete)
   - NO → block exit, re-inject prompt with previous output context, increment iteration counter
5. Ceiling: after 10 iterations, hook writes failure log and allows exit

**Implementation**:
- Stop hook: `.claude/hooks/stop.py` — reads task state file, checks `/Done`, re-injects
- Completion strategy: File-movement based (not promise-based) — more reliable as it's
  a natural part of the vault workflow
- State file tracks: `prompt`, `task_ref`, `iteration_count`, `max_iterations: 10`

**Alternatives considered**:
- Promise-based (`<promise>TASK_COMPLETE</promise>`) — simpler but Claude can hallucinate completion
- External polling loop — less integrated with Claude Code's native hook system

---

## Decision 3: MCP Server Transport

**Decision**: stdio transport (standard I/O) for all MCP servers

**Rationale**:
- Native Claude Code MCP configuration uses stdio by default
- Zero network overhead, no port conflicts
- Simplest deployment — process spawned by Claude Code on demand
- Claude Code's `mcp.json` config handles process lifecycle
- Compatible with both local and Cloud VM deployments

**Server framework**: Node.js MCP SDK (`@modelcontextprotocol/sdk`) for email/browser/calendar;
Python MCP SDK (`mcp`) for Odoo MCP (better httpx/JSON-RPC integration)

**Alternatives considered**:
- SSE (Server-Sent Events) transport — unnecessary for single-user, adds complexity
- HTTP transport — same as above; overkill for local use case

---

## Decision 4: Gmail Integration

**Decision**: Google API Python client (`google-api-python-client`) with OAuth 2.0 + refresh tokens

**Rationale**:
- Official Google API — stable, well-documented, free tier sufficient
  (Gmail API: 250 quota units/user/second; list/get = 5 units; send = 100 units)
- Refresh tokens prevent re-authentication after initial setup
- `credentials.json` stored outside vault (env var `GMAIL_CREDENTIALS_PATH`)
- Polling interval: 120 seconds (FR-001) — well within rate limits

**Auth setup**:
1. Create OAuth 2.0 Client ID in Google Cloud Console (Desktop app type)
2. Enable Gmail API
3. Run one-time auth flow: saves `token.json` to path in `.env`
4. Watcher loads refresh token automatically on each poll

**Query filter**: `is:unread is:important` — reduces noise, targets high-priority items

**Alternatives considered**:
- IMAP/SMTP — no push/query filtering, no structured API, credential handling differs
- Gmail API with push notifications (Pub/Sub) — more complex setup, better for production;
  deferred to post-hackathon optimization

---

## Decision 5: WhatsApp Integration

**Decision**: Playwright persistent browser context against WhatsApp Web

**Rationale**:
- No official WhatsApp API for personal accounts (Business API requires business verification)
- Playwright persistent context preserves session across restarts (avoids QR re-scan)
- Session path stored outside vault (env var `WHATSAPP_SESSION_PATH`)
- Polling interval: 30 seconds (FR-002)

**Risk mitigation**:
- WhatsApp ToS — use for personal/demo purposes only; not for commercial automation
- Headless mode for Cloud VM; headed mode optional locally
- If session invalidated: watcher stops, writes `/Logs/` error, writes
  `/Needs_Action/ALERT_wa_session_loss_<ts>.md`, does NOT retry indefinitely

**Session pattern**:
```python
browser = playwright.chromium.launch_persistent_context(
    session_path, headless=True, args=["--no-sandbox"]
)
```

**Alternatives considered**:
- WhatsApp Business API — requires Meta business verification; not feasible for hackathon
- `pywhatkit` / unofficial libs — unmaintained, fragile, ToS risk

---

## Decision 6: Social Media APIs

**Decision**: Official OAuth APIs for all platforms; graceful degradation on tier limits

| Platform | API | Auth | Free Tier Notes |
|----------|-----|------|-----------------|
| LinkedIn | LinkedIn API v2 (Marketing + Share) | OAuth 2.0 | 500 requests/day |
| Facebook | Facebook Graph API v19+ | OAuth 2.0 / App Token | Page-level posting |
| Instagram | Instagram Graph API | OAuth 2.0 (via Facebook) | Requires Business/Creator account |
| Twitter/X | Twitter API v2 | OAuth 2.0 (bearer + user) | Free: 1,500 posts/month read; 50 writes/day |

**Degradation behavior** (FR-023): If API limit exceeded → log limitation to `/Logs/` →
include note in CEO Briefing section ("LinkedIn data unavailable — API limit reached") →
continue audit without failing

**Rationale**: Official APIs are stable, auditable, and ToS-compliant. All platforms
require OAuth 2.0 app registration; credentials stored as env vars, never in vault.

**Alternatives considered**:
- Playwright scraping for social — fragile on layout changes, ToS risk, detection-prone
- Unofficial Python libraries — unmaintained, credential-unsafe

---

## Decision 7: Banking/Finance Data Source

**Decision**: CSV file drop into `/Accounting/` — Finance Watcher parses using Python `csv` module

**Rationale**:
- Zero API risk and complexity (clarification Q5 answer)
- Compatible with any bank's CSV export format
- Privacy-safe — data never leaves local machine
- Finance Watcher uses `watchdog` to detect new `.csv` files; parses with `csv.DictReader`
- Writes structured entries to `/Accounting/Current_Month.md` for CEO Briefing

**CSV column mapping**: configurable via `FINANCE_CSV_COLUMNS` in `.env`
(e.g., `date,description,amount,balance` — banks vary in column names)

**Alternatives considered**:
- Open Banking APIs (UK/EU PSD2) — bank-specific OAuth, complex, not globally applicable
- Plaid — paid service, US-focused, overkill for hackathon
- Live bank API scraping — ToS risk, fragile

---

## Decision 8: Odoo Integration (Gold+)

**Decision**: Odoo 19+ External JSON-RPC API (`/web/dataset/call_kw` endpoint)

**Rationale**:
- Official Odoo API — works with Community Edition (no Enterprise license needed)
- Stable, versioned, well-documented (`/documentation/19.0/developer/reference/external_api.html`)
- Supports CRUD on all Odoo models (invoices, partners, accounting entries)
- Authentication: API key (Odoo 17+) — stored as `ODOO_API_KEY` env var
- Cloud agent uses draft-only calls; Local agent approves posting

**Key calls**:
```python
# Search + read (safe, cloud-allowed)
POST /web/dataset/call_kw
{"model": "account.move", "method": "search_read", ...}

# Create draft (cloud-allowed)
{"model": "account.move", "method": "create", "args": [{"state": "draft", ...}]}

# Post/confirm (Local only, requires approval)
{"model": "account.move", "method": "action_post", "args": [[invoice_id]]}
```

**Alternatives considered**:
- Odoo REST API — only available in Odoo 17+ Enterprise; Community uses JSON-RPC
- XML-RPC — deprecated in Odoo 17+, do not use for Odoo 19+

---

## Decision 9: Vault Sync for Platinum

**Decision**: Git-based sync (private GitHub/GitLab repo) with `.gitignore` for secrets

**Rationale**:
- Proven, free, native to the developer workflow
- `.gitignore` provides deterministic exclusion of secrets (FR-025)
- Full audit trail via commit history
- Cloud VM can `git pull` on schedule; local can `git push` after actions

**`.gitignore` required entries**:
```gitignore
.env
vault_template/State/
vault_template/Logs/     # optional — may want to sync logs
*.session                # WhatsApp sessions
token.json               # Gmail OAuth tokens
```

**Sync cadence**: `git push` after every Local action; Cloud `git pull` every 5 minutes via cron

**Alternatives considered**:
- Syncthing — no audit trail, no `.gitignore` equivalent for selective exclusion
- Dropbox/OneDrive — no programmatic `.gitignore` control, secret exposure risk

---

## Decision 10: Python Project Structure

**Decision**: UV Python project (`uv init`) with `pyproject.toml`, `src/` layout

**Rationale**:
- `uv` is the hackathon-specified package manager (pre-hackathon checklist)
- `src/` layout prevents accidental imports from project root
- `pyproject.toml` centralizes all metadata + dependencies
- Windows 10 compatible; same tooling on Cloud VM

**Alternatives considered**:
- `pip` + `requirements.txt` — less structured, no virtual env management
- `poetry` — heavier than needed for a hackathon project

---

## Decision 11: Agent Skills (SKILL.md) Format

**Decision**: Claude Code Agent Skills in `.claude/` directory per platform docs

**Format** (per `platform.claude.com/docs/en/agents-and-tools/agent-skills/overview`):
```markdown
---
name: email-triage
description: Triage incoming emails from /Needs_Action and create Plans
version: 1.0.0
inputs:
  - name: action_file_path
    type: string
    description: Path to the EMAIL_*.md action file in /Needs_Action
outputs:
  - name: plan_file_path
    type: string
    description: Path to the Plan.md created in /Plans
---

## Skill: Email Triage

[Skill instructions here...]
```

**Skills to implement** (FR-027):
- `email-triage.md` — read action file, classify, create Plan.md
- `invoice-generator.md` — generate invoice from client data, create approval file
- `ceo-briefing.md` — run weekly audit, generate CEO Briefing
- `vault-monitor.md` — check /Needs_Action, claim tasks, execute Ralph loop
- `approval-handler.md` — detect /Approved files, trigger MCP, log, move to /Done

---

## Decision 12: Watcher Idempotency (Clarification Q3 Answer)

**Decision**: File-based state — each watcher writes processed IDs to `/State/<watcher_name>.json`

**Format**: `{"watcher": "gmail", "processed_ids": ["<id1>", ...], "last_updated": "ISO8601"}`

**Rationale**:
- Survives process crashes and restarts (unlike in-memory sets)
- Simple JSON read/write — no database dependency
- Each watcher loads its state file on startup, extends the set, and saves after each batch

**Write strategy**: Append-only with periodic compaction (after 10,000 IDs, drop IDs older
than 30 days to prevent unbounded growth)

---

---

## Supplement: Research Agent Findings (Post-Write Additions)

*These findings arrived after research.md was drafted. Key deltas incorporated below.*

### Gmail — History ID Optimization

Use `history.list(historyTypes=['messageAdded'])` with a stored `startHistoryId` instead
of full `messages.list()` on each poll. This reduces quota consumption by ~90%+ since only
changes since the last poll are returned. Store `historyId` in `/State/gmail_watcher.json`
after each call. Handle `INVALID_START_HISTORY_ID` (history garbage-collected after ~30 days)
by falling back to full list + re-seeding the history ID.

### WhatsApp — headless=False Required

WhatsApp Web detects and blocks fully headless Chrome via automation fingerprint detection.
Required flags:
```python
args=["--disable-blink-features=AutomationControlled"]
headless=False  # on Windows/local; use xvfb-run on Linux Cloud VM
# Cloud VM: DISPLAY=:99 xvfb-run python whatsapp_watcher.py
```
Session expiry detection: monitor for "Phone not connected" modal or URL redirect to `/`.

### Twitter/X Free Tier — Severe Limits

Free tier: **50 API requests/month total** and 1,500 tweets/month. This is extremely
limited. Recommendation: use Twitter/X only for posting (not reading engagement for CEO
Briefing) on free tier. Degrade gracefully per FR-023: log limitation, include note in
briefing, continue audit.

### CSV Parsing — Use pandas, Not csv Module

`pandas.read_csv()` with `infer_datetime_format=True` handles bank-specific CSV variations
far better than `csv.DictReader`. Common pitfalls to handle:
- Negative amounts as `(100)` — normalize with regex
- Duplicate transactions when statement periods overlap — deduplicate on `(Date, Amount, Description)`
- Encoding: try UTF-8, fall back to Latin-1

Common bank CSV column mappings (configurable via `FINANCE_CSV_COLUMNS` in `.env`):

| Bank type | Date col | Amount col | Description col |
|-----------|----------|------------|-----------------|
| Generic | Date | Amount | Description |
| Chase | Date | Amount | Description |
| BOA | Date | Amount | Description |

Use `pandas` `subscription_keywords` pattern matching for CEO Briefing audit logic.

### Odoo — Session Auth vs API Key

Session-based auth (login → session cookie) lasts 8+ hours and avoids API key in request
headers. Preferred for long-running Cloud agent. API key auth (simpler) recommended for
hackathon. Many-to-many fields (e.g., `line_ids` on invoices) require special format:
`[[6, 0, [id1, id2]]]` for replace operations. Always use UTC for datetime fields.

---

## Summary: All NEEDS CLARIFICATION Resolved

| Item | Resolution |
|------|-----------|
| API rate limit handling | Exponential backoff + local queue + ALERT file + auto-resume |
| Critical failure alerts | email-mcp to owner + ALERT_*.md in vault |
| Watcher ID persistence | File-based `/State/<watcher>.json` |
| Social media APIs | Official OAuth APIs; graceful degradation |
| Banking data source | CSV file drop into `/Accounting/` |
| Process manager | PM2 (cross-platform Windows + Linux) |
| MCP transport | stdio (native Claude Code integration) |
| Vault sync | Git with `.gitignore` secrets exclusion |
| Odoo API | JSON-RPC `/web/dataset/call_kw` |
| Project structure | UV + pyproject.toml + src/ layout |
| SKILL.md format | Claude Code Agent Skills in `.claude/` |
