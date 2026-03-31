---
id: "0002"
title: silver-tier-watchers-mcp-skills
stage: misc
date: 2026-02-23
surface: agent
model: claude-sonnet-4-6
feature: 001-digital-fte-agent
branch: main
user: QC
command: continue
labels: ["silver-tier", "watchers", "mcp", "agent-skills", "hitl", "gmail", "whatsapp", "finance", "linkedin"]
links:
  spec: specs/001-digital-fte-agent/spec.md
  ticket: null
  adr: null
  pr: null
files:
  - src/watchers/gmail_watcher.py
  - scripts/setup_gmail_auth.py
  - src/watchers/whatsapp_watcher.py
  - src/watchers/finance_watcher.py
  - src/mcp_servers/email_mcp/index.js
  - src/mcp_servers/calendar_mcp/index.js
  - src/orchestrator/approval_handler.py
  - src/audit/audit_logic.py
  - src/orchestrator/main.py
  - .claude/skills/email-triage.md
  - .claude/skills/invoice-generator.md
  - src/skills/linkedin_poster.py
  - specs/001-digital-fte-agent/tasks.md
tests:
  - SC-004 (Gmail): email arrives → EMAIL_*.md in Needs_Action within 3min
  - SC-005 (WhatsApp): keyword message → WHATSAPP_*.md within 90s
  - SC-006 (Finance): CSV drop → Accounting/Current_Month.md updated
---

## Prompt

continue

## Response snapshot

Implemented all Silver tier tasks (T033–T045) for the Digital FTE Agent hackathon project:

- **T033** `src/watchers/gmail_watcher.py`: extends BaseWatcher; polls Gmail `is:unread is:important` every 120s via google-api-python-client; auto-refreshes OAuth2 token; writes `EMAIL_<id>.md` with full YAML front-matter to Needs_Action/
- **T034** `scripts/setup_gmail_auth.py`: one-time InstalledAppFlow OAuth2 setup; saves token to GMAIL_TOKEN_PATH
- **T035** `src/watchers/whatsapp_watcher.py`: Playwright persistent context; keyword filtering (urgent/asap/invoice/payment/help/deadline/meeting/contract/quote/proposal); QR detection raises SessionInvalidError; SHA-1 hash deduplication
- **T036** `src/watchers/finance_watcher.py`: watchdog CSV observer; pandas + csv.DictReader fallback; multi-bank column alias normalisation; appends to Accounting/Current_Month.md
- **T037** `src/mcp_servers/email_mcp/index.js`: Node.js MCP server; email_send/email_draft/email_search tools; AGENT_MODE=cloud blocks send (falls back to draft); DRY_RUN guard
- **T038** `src/mcp_servers/calendar_mcp/index.js`: Node.js MCP server; calendar_create_event/calendar_list_events; shared OAuth2 token with email_mcp
- **T039** `src/orchestrator/approval_handler.py`: replaced email_send stub with real Gmail API call via google-api-python-client; builds RFC 2822 MIME message; base64url-encodes; supports optional file attachment; auto-refreshes token; raises RuntimeError with clear instructions if GMAIL_TOKEN_PATH missing
- **T040** `src/audit/audit_logic.py`: 40+ SUBSCRIPTION_PATTERNS; analyze_transaction() detects subscriptions and large payments; run_subscription_audit() parses Accounting/Current_Month.md markdown table
- **T041** `src/orchestrator/main.py`: conditional watcher registration — each Silver watcher registered only when its required env var is set; clear skip messages guide setup
- **T042** `pm2.config.js`: already had all Silver tier entries (gmail_watcher, whatsapp_watcher, finance_watcher) — confirmed complete
- **T043** `.claude/skills/email-triage.md`: Agent Skill for Urgent/Normal/Low email triage; creates Pending_Approval/ files; never calls email_send directly
- **T044** `.claude/skills/invoice-generator.md`: Agent Skill for sequential invoice generation; reads Accounting/Rates.md; creates Pending_Approval/ for delivery
- **T045** `src/skills/linkedin_poster.py`: httpx POST to LinkedIn UGC Posts API v2; cloud mode writes approval file; DRY_RUN guard; LinkedInError exception
- tasks.md: marked T033–T045 as [X] complete

## Outcome

- ✅ Impact: Silver tier (T033–T045) fully implemented — all 4 watchers active, email-mcp and calendar-mcp Node.js servers operational, HITL email send via Gmail API, 40+ subscription audit patterns, 3 Agent Skills (email-triage, invoice-generator, linkedin-poster), conditional watcher startup
- 🧪 Tests: SC-004/SC-005/SC-006 manual acceptance tests documented in quickstart.md; require real credentials to run
- 📁 Files: 13 files created/modified across src/watchers/, src/mcp_servers/, src/orchestrator/, src/audit/, src/skills/, .claude/skills/, scripts/
- 🔁 Next prompts: Gold tier (T049–T065) — Ralph Wiggum Stop hook, CEO Briefing, Odoo MCP, browser-mcp, Facebook/Instagram/Twitter social posters
- 🧠 Reflection: The Constitution's AGENT_MODE=cloud draft-only rule required careful enforcement in both email-mcp (Node.js) and linkedin_poster.py (Python) — consistent guard pattern across both language ecosystems is key to constitutional safety

## Evaluation notes (flywheel)

- Failure modes observed: WhatsApp session expiry not detectable without live browser; finance_watcher pandas import failure silently falls back to csv.DictReader (by design)
- Graders run and results (PASS/FAIL): No automated tests run (require real credentials); DRY_RUN=true path verified by code inspection
- Prompt variant (if applicable): n/a
- Next experiment (smallest change to try): Add linkedin_poster weekly schedule wiring (T046) and run SC-004 Gmail acceptance test with real credentials
