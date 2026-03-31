# Digital FTE — Personal AI Employee

> **Tier: Platinum** | Python 3.13+ · Node.js v24+ · Claude Code · Obsidian Vault

A local-first AI employee that monitors your Gmail, WhatsApp, filesystem, and
bank statements; takes external actions via MCP servers; enforces a human-in-
the-loop approval gate for every sensitive action; and runs 24/7 via a
Cloud/Local dual-agent architecture.

---

## Architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│                        LOCAL AGENT (Claude Code)                     │
│                                                                       │
│  ┌───────────────── Perception Layer ─────────────────┐              │
│  │  FilesystemWatcher  GmailWatcher  WhatsAppWatcher  │              │
│  │              FinanceWatcher                        │              │
│  └──────────────────────┬─────────────────────────────┘              │
│                         │ Needs_Action/*.md                           │
│  ┌──────────────── Obsidian Vault ────────────────────┐              │
│  │  Needs_Action/  In_Progress/  Pending_Approval/    │              │
│  │  Approved/      Done/         Dashboard.md         │              │
│  │  Plans/         Briefings/    Accounting/          │              │
│  └──────────────────────┬─────────────────────────────┘              │
│                         │                                             │
│  ┌──────────────── Action Layer (MCP) ────────────────┐              │
│  │  email-mcp (Node.js)   calendar-mcp (Node.js)      │              │
│  │  odoo-mcp  (Python)    browser-mcp  (Node.js)      │              │
│  └──────────────────────┬─────────────────────────────┘              │
│                         │ Approval gate (HITL)                        │
│  ┌──────────────── Orchestrator ──────────────────────┐              │
│  │  ApprovalHandler · Ralph Wiggum Stop Hook          │              │
│  │  CEO Briefing (Sun 22:00) · Social Post (Mon 09:30)│              │
│  └────────────────────────────────────────────────────┘              │
└─────────────────────────────────────────────────────────────────────┘
                          Git vault sync (15 min)
┌─────────────────────────────────────────────────────────────────────┐
│                    CLOUD AGENT (Oracle/AWS VM)                        │
│  GmailWatcher · FinanceWatcher · Orchestrator (cloud mode)           │
│  Draft-only — cannot send_email / execute_payment                    │
│  Writes Pending_Approval/ files → Local agent approves & executes   │
└─────────────────────────────────────────────────────────────────────┘
```

---

## Tier Descriptions

| Tier | What it delivers |
|------|-----------------|
| **Bronze** | Filesystem watcher, Obsidian vault lifecycle (Needs_Action → In_Progress → Done), Dashboard updates, HITL approval gate |
| **Silver** | Gmail + WhatsApp + Finance watchers, email-mcp, calendar-mcp, LinkedIn posting, invoice-generator skill |
| **Gold** | CEO Briefing, Odoo ERP MCP, Facebook/Instagram/Twitter social, Ralph Wiggum persistence loop, browser-mcp, subscription audit |
| **Platinum** | Cloud/Local dual-agent separation, Git vault sync, claim-by-move multi-agent coordination, 24/7 always-on operation |

---

## Quick Start

### Prerequisites

- Python 3.13+
- Node.js v24+ LTS
- [uv](https://docs.astral.sh/uv/) (`pip install uv`)
- PM2 (`npm install -g pm2`)
- [Obsidian](https://obsidian.md/download) v1.10.6+
- Playwright browsers: `uv run playwright install chromium`

### 1. Clone & install

```bash
git clone <repo-url> digital_FTE
cd digital_FTE
uv sync
npm install --prefix src/mcp_servers/email_mcp
npm install --prefix src/mcp_servers/calendar_mcp
npm install --prefix src/mcp_servers/browser_mcp
```

### 2. Configure environment

```bash
cp .env.example .env
# Edit .env — set VAULT_PATH, Gmail, WhatsApp, and social credentials
```

Key variables:

| Variable | Description |
|----------|-------------|
| `VAULT_PATH` | Absolute path to your Obsidian vault directory |
| `GMAIL_CLIENT_ID` / `GMAIL_CLIENT_SECRET` | Google Cloud OAuth credentials |
| `GMAIL_TOKEN_PATH` | Path where OAuth token will be saved |
| `WHATSAPP_SESSION_PATH` | Persistent Playwright profile for WhatsApp Web |
| `BANK_CSV_DROP_PATH` | Folder to drop bank statement CSVs |
| `LINKEDIN_ACCESS_TOKEN` | LinkedIn OAuth access token |
| `LINKEDIN_AUTHOR_URN` | `urn:li:person:<sub>` from LinkedIn `/v2/userinfo` |
| `TWITTER_CONSUMER_KEY` | Twitter/X API key (OAuth 1.0a) |
| `TWITTER_CONSUMER_KEY_SECRET` | Twitter/X API secret |
| `TWITTER_ACCESS_TOKEN` | Twitter/X access token |
| `TWITTER_ACCESS_TOKEN_SECRET` | Twitter/X access token secret |
| `DRY_RUN` | `true` (default) — no live API calls; set `false` for production |
| `AGENT_MODE` | `local` (default) or `cloud` |

### 3. Initialize vault

```bash
uv run python scripts/setup_vault.py
# Open VAULT_PATH as an Obsidian vault
```

### 4. Authenticate Gmail

```bash
uv run python scripts/setup_gmail_auth.py
```

### 5. Authenticate WhatsApp

```bash
uv run python scripts/setup_whatsapp_session.py
# Scan QR code in the browser window that opens
```

### 6. Start all watchers

```bash
pm2 start pm2.config.js
pm2 status
```

### 7. Run acceptance tests

```bash
uv run pytest tests/test_foundation.py -v
uv run python tests/test_bronze_acceptance.py
uv run python tests/test_silver_acceptance.py
uv run python scripts/test_platinum_gate.py
```

---

## Cloud VM Deployment (Platinum)

```bash
# On Oracle/AWS Ubuntu 22.04 VM:
bash scripts/setup_cloud_agent.sh

# Start cloud watchers only:
pm2 start pm2.cloud.config.js
```

See `.env.cloud.example` for cloud-specific environment variables.

---

## Security Disclosure

- **DRY_RUN=true by default** — no live API calls until you explicitly set `DRY_RUN=false`
- **HITL approval gate** — every sensitive action (email send, payment, social post) writes a `Pending_Approval/` file and waits for user approval before executing
- **Credential handling** — all secrets via `.env` only; never committed to git; never written to vault markdown
- **Cloud constraints** — Cloud agent enforces `draft-only` mode at startup: `send_email`, `send_payment`, and `execute_payment` are blocked; only Local agent can execute
- **Vault sync exclusions** — `.env`, `State/*.json`, `WhatsApp Session/` are excluded from Git vault sync via `vault_template/.gitignore`
- **Audit trail** — every action logged to `VAULT_PATH/Logs/YYYY-MM-DD.json` with 90-day retention

---

## Demo Video

<!-- TODO: Record 5–10 minute demo covering Bronze→Platinum tier highlights -->
*Demo video link — coming soon*

---

## Project Structure

```
digital_FTE/
├── src/
│   ├── watchers/          # Filesystem, Gmail, WhatsApp, Finance watchers
│   ├── orchestrator/      # Orchestrator, ApprovalHandler, cloud constraints
│   ├── skills/            # LinkedIn, Twitter, Facebook, Instagram posters
│   ├── mcp_servers/       # email-mcp, calendar-mcp, odoo-mcp, browser-mcp
│   ├── audit/             # AuditLogger, CEO Briefing, subscription audit
│   ├── vault_utils.py     # Vault file operations with lock/atomic writes
│   ├── state_manager.py   # Watcher idempotency state
│   ├── retry_handler.py   # Exponential backoff decorator
│   ├── dry_run.py         # DRY_RUN guard
│   └── exceptions.py      # Custom exception hierarchy
├── specs/                 # Spec-Driven Development artifacts
├── scripts/               # Setup and utility scripts
├── tests/                 # Acceptance tests (Bronze → Platinum)
├── vault_template/        # Obsidian vault scaffolding
├── .claude/               # Agent skills and hooks
│   ├── hooks/stop.py      # Ralph Wiggum persistence loop
│   └── skills/            # vault-monitor, email-triage, invoice-generator, etc.
├── pm2.config.js          # Local process manager config
├── pm2.cloud.config.js    # Cloud VM process manager config
└── .env.example           # Environment variable template
```

---

## Tech Stack

| Layer | Technology |
|-------|-----------|
| Reasoning engine | Claude Code (claude-sonnet-4-6) |
| Watchers | Python 3.13+, watchdog, Playwright, google-api-python-client, pandas |
| MCP servers | Node.js v24+ (email, calendar, browser), Python FastMCP (Odoo) |
| Vault / memory | Obsidian v1.10.6+ (local Markdown) |
| Process manager | PM2 |
| Package manager | uv (Python), npm (Node.js) |
| Audit / state | NDJSON logs, JSON state files |
| Vault sync | Git (15-minute cron, Cloud→Local) |
| Cloud VM | Oracle/AWS Ubuntu 22.04 LTS |
