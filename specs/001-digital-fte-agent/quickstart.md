# Quickstart: Digital FTE Agent

**Branch**: `001-digital-fte-agent` | **Date**: 2026-02-22

This guide gets the Digital FTE Agent running locally from scratch. Follow each tier
section in order — each tier builds on the previous.

---

## Prerequisites

| Requirement | Version | Check |
|-------------|---------|-------|
| Python | 3.13+ | `python --version` |
| Node.js | v24+ LTS | `node --version` |
| uv | latest | `uv --version` |
| PM2 | latest | `pm2 --version` |
| Claude Code | latest | `claude --version` |
| Obsidian | v1.10.6+ | Open and verify |
| Git | latest | `git --version` |

**Install PM2 globally** (if not installed):
```bash
npm install -g pm2
```

---

## Step 1: Clone and Configure Environment

```bash
git clone <your-repo-url>
cd digital_FTE
```

Copy and fill the environment file:
```bash
cp .env.example .env
```

Edit `.env` with your values:
```bash
# Vault
VAULT_PATH=C:/Users/<you>/Documents/AI_Employee_Vault

# Gmail OAuth (see Step 3)
GMAIL_CREDENTIALS_PATH=C:/Users/<you>/.secrets/gmail_credentials.json
GMAIL_TOKEN_PATH=C:/Users/<you>/.secrets/gmail_token.json

# WhatsApp
WHATSAPP_SESSION_PATH=C:/Users/<you>/.secrets/whatsapp_session

# Odoo (Gold+)
ODOO_URL=http://localhost:8069
ODOO_DB=my_company
ODOO_API_KEY=your_odoo_api_key

# Owner email for critical alerts
OWNER_EMAIL=you@gmail.com

# Safety (set to false when confident)
DRY_RUN=true
```

---

## Step 2: Set Up Python Project

```bash
uv init
uv sync
```

If `pyproject.toml` does not exist yet:
```bash
uv init --name digital-fte
uv add google-api-python-client google-auth-oauthlib playwright watchdog \
        python-dotenv httpx tweepy pytest pytest-asyncio
playwright install chromium
```

---

## Step 3: Initialize Obsidian Vault

1. Open Obsidian → "Open folder as vault" → navigate to your `VAULT_PATH`
2. Copy the vault template structure:
```bash
python scripts/init_vault.py
```

This creates:
```
/Needs_Action/    /In_Progress/local/    /In_Progress/cloud/
/Done/            /Logs/                 /Plans/
/Pending_Approval/ /Approved/            /Rejected/
/Briefings/       /State/               /Accounting/
/Updates/         Dashboard.md          Company_Handbook.md
Business_Goals.md
```

3. Edit `Company_Handbook.md` with your rules of engagement
4. Edit `Business_Goals.md` with your revenue targets and metrics

---

## Step 4: Gmail OAuth Setup

1. Go to [Google Cloud Console](https://console.cloud.google.com/)
2. Create project → Enable **Gmail API**
3. Create OAuth 2.0 Client ID (Desktop app type)
4. Download `credentials.json` to `GMAIL_CREDENTIALS_PATH`
5. Run one-time auth flow:
```bash
python scripts/gmail_auth.py
```
   → Browser opens → sign in → `token.json` saved to `GMAIL_TOKEN_PATH`
6. Verify: `python scripts/test_gmail_connection.py` — should list recent emails

---

## Step 5: Bronze Tier — Run File System Watcher

**Test the core perception loop:**

Terminal 1 — Start the filesystem watcher:
```bash
uv run python src/watchers/filesystem_watcher.py
```

Terminal 2 — Drop a test file:
```bash
# Drop any file into your VAULT_PATH/drop_inbox/ folder
# The watcher should create a FILE_*.md in /Needs_Action within 60 seconds
```

Terminal 3 — Trigger Claude to process it:
```bash
claude --cwd "$VAULT_PATH" "Check /Needs_Action and process any pending items"
```

**Expected outcome**: File moves through `/Needs_Action` → `/In_Progress/local/` → `/Done`.
`Dashboard.md` updated. Audit entry written to `/Logs/`.

**SC-001 Acceptance Test**: Drop a file, verify action item appears in < 60 seconds.

---

## Step 6: Silver Tier — Start All Watchers with PM2

Start all Watchers using PM2 (auto-restart on crash):
```bash
pm2 start pm2.config.js
pm2 save        # persist across reboots
pm2 startup     # configure OS startup (follow the printed instructions)
```

Verify watchers are running:
```bash
pm2 list
pm2 logs gmail-watcher    # check for errors
```

**WhatsApp setup**:
```bash
uv run python src/watchers/whatsapp_watcher.py --setup
```
→ Browser opens with WhatsApp Web → scan QR code → session saved to `WHATSAPP_SESSION_PATH`

Restart after setup:
```bash
pm2 restart whatsapp-watcher
```

**Test MCP email sending** (DRY_RUN=true first):
```bash
claude --cwd "$VAULT_PATH" "Draft a reply to the latest email in /Needs_Action"
```
→ Verify `/Pending_Approval/EMAIL_*.md` is created (NOT sent yet).
→ Move file to `/Approved/` to trigger send.

---

## Step 7: Gold Tier — Configure MCP Servers

Install Node.js MCP server dependencies:
```bash
cd src/mcp_servers/email_mcp && npm install
cd ../browser_mcp && npm install
cd ../calendar_mcp && npm install
cd ../..
```

Update Claude Code MCP config:
```bash
claude mcp add email node src/mcp_servers/email_mcp/index.js
claude mcp add browser node src/mcp_servers/browser_mcp/index.js
claude mcp add calendar node src/mcp_servers/calendar_mcp/index.js
```

**Test email MCP (dry run)**:
```bash
DRY_RUN=true claude --cwd "$VAULT_PATH" \
  "Send a test email to $OWNER_EMAIL with subject 'Digital FTE Test'"
```
→ Verify log shows `[DRY RUN] Would send email`.

**Set DRY_RUN=false** in `.env` when confident:
```bash
# .env
DRY_RUN=false
```

---

## Step 8: Gold Tier — Run the CEO Briefing

Manually trigger the weekly audit:
```bash
claude --cwd "$VAULT_PATH" \
  "Run the weekly CEO Briefing audit for the period 2026-02-16 to 2026-02-22"
```

**Prerequisites** for a meaningful briefing:
- `Business_Goals.md` — revenue targets and project list
- `/Accounting/Current_Month.md` — populated by Finance Watcher from CSV drop
- `/Done/` — completed task files from the week

**Expected output**: `/Briefings/2026-02-22_Monday_Briefing.md` with all sections.

**SC-007 Acceptance Test**: Verify briefing is generated within 10 minutes with
Executive Summary, Revenue, Completed Tasks, Bottlenecks, and Proactive Suggestions.

---

## Step 9: Gold Tier — Install Odoo MCP (Optional)

```bash
cd src/mcp_servers/odoo_mcp
uv sync
uv run python odoo_mcp.py --test    # verify connection to Odoo
claude mcp add odoo python src/mcp_servers/odoo_mcp/odoo_mcp.py
```

---

## Step 10: Ralph Wiggum Loop Setup

The Ralph Wiggum Stop hook is configured in `.claude/settings.json`:

```json
{
  "hooks": {
    "stop": {
      "command": "python .claude/hooks/stop.py"
    }
  }
}
```

Deploy the stop hook:
```bash
cp src/hooks/stop.py .claude/hooks/stop.py
```

Test with a multi-step task:
```bash
claude --cwd "$VAULT_PATH" \
  "Process all items in /Needs_Action and move each to /Done when complete. \
   Track progress in /State/ralph_task_test.json"
```

---

## Step 11: Deploy Agent Skills

Copy skills to `.claude/`:
```bash
cp src/skills/*.md .claude/
```

Verify skills are recognized:
```bash
claude --cwd "$VAULT_PATH" --print "/list-skills"
```

Expected skills visible: `email-triage`, `invoice-generator`, `ceo-briefing`,
`vault-monitor`, `approval-handler`

---

## Step 12: Platinum Tier — Cloud VM Setup

On Oracle Cloud / AWS Linux VM:

```bash
# Install Node.js, Python, PM2, Git, uv
# (same versions as local)

git clone <your-vault-repo> vault/
cd <project-dir>
git clone <your-source-repo> .

# Configure .env for Cloud agent
# IMPORTANT: NO banking creds, NO WhatsApp session path on Cloud
cp .env.example .env.cloud
# Edit .env.cloud — set AGENT_MODE=cloud

# Start Cloud-only watchers (Gmail + Filesystem only)
pm2 start pm2.cloud.config.js
pm2 save && pm2 startup
```

**Vault sync** (cron on Cloud VM):
```bash
# /etc/cron.d/vault-sync
*/5 * * * * cd /path/to/vault && git pull --rebase --autostash
```

**Platinum acceptance test**:
1. Shut down local machine
2. Send email to Gmail account
3. Wait 5 minutes
4. Verify `/Updates/EMAIL_draft_*.md` created on Cloud (via git log on GitHub)
5. Start local machine, `git pull`
6. Approve the `/Pending_Approval/` file
7. Verify Local sends via MCP, logs, moves to `/Done`

---

## Troubleshooting

| Issue | Diagnosis | Fix |
|-------|-----------|-----|
| Watcher not creating files | `pm2 logs <name>` | Check `.env` VAULT_PATH; check API creds |
| Gmail 403 | Cloud Console | Enable Gmail API; verify OAuth consent screen |
| WhatsApp session invalid | ALERT file in /Needs_Action | Re-run `--setup`, re-scan QR |
| MCP not connecting | `claude mcp list` | Verify path in `mcp.json`; check Node.js version |
| Action item duplicated | `/State/*.json` | Check if state file was corrupted; rebuild from scratch |
| CEO Briefing fails | Ralph iteration count | Check `/Plans/` for failed plan; inspect Claude logs |
| Cloud/Local conflict | `/In_Progress/` | Verify claim-by-move is implemented in orchestrator |
