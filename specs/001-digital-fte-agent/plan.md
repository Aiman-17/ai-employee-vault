# Implementation Plan: Digital FTE Agent — Personal AI Employee

**Branch**: `001-digital-fte-agent` | **Date**: 2026-02-22 | **Spec**: [spec.md](spec.md)
**Input**: Feature specification from `/specs/001-digital-fte-agent/spec.md`

## Summary

Build a local-first Personal AI Employee using Claude Code as the reasoning engine, an
Obsidian vault as memory/dashboard, Python Sentinel Watchers as the perception layer,
and MCP servers as the action layer. Target tier is Platinum (all 4 tiers delivered
incrementally). Bronze establishes vault + watcher foundation; Silver adds multi-watcher
+ MCP + HITL; Gold adds CEO Briefing + Odoo + social integrations + Ralph Wiggum loop;
Platinum adds Cloud/Local separation with 24/7 always-on operation.

## Technical Context

**Language/Version**: Python 3.13+ (Watchers, Orchestrator, Audit), Node.js v24+ LTS (MCP servers)
**Primary Dependencies**:
- `google-api-python-client` + `google-auth-oauthlib` — Gmail Watcher
- `playwright` — WhatsApp Watcher and browser-mcp
- `watchdog` — File System Watcher (filesystem events)
- `python-dotenv` — Environment configuration
- `httpx` — Odoo MCP HTTP client
- `tweepy` — Twitter/X API v2
- `facebook-sdk` — Facebook Graph API + Instagram Graph API
- `PM2` (Node.js global) — Process manager for all Watchers
- `pytest` + `pytest-asyncio` — Python testing
- `uv` — Python package/project manager (per hackathon prereqs)
- `fastmcp` or MCP Python SDK — MCP server implementation

**Storage**: Obsidian vault (local Markdown as source of truth), `/State/*.json` (Watcher
idempotency state), `/Logs/*.json` (audit trail, 90-day retention), Git (vault sync for Platinum)

**Testing**: pytest (unit + integration), manual acceptance testing mapped to SC-001→SC-014

**Target Platform**: Windows 10 (local agent + development), Ubuntu 22.04 LTS (Cloud VM — Oracle/AWS)

**Project Type**: Single monorepo (multi-module Python + Node.js MCP servers)

**Performance Goals**:
- File Watcher detection: < 60 seconds (SC-001)
- Gmail action item creation: < 3 minutes from email arrival (SC-004)
- WhatsApp action item creation: < 90 seconds from message (FR-002)
- CEO Briefing generation: < 10 minutes from scheduled trigger (SC-007)
- Watcher auto-restart after crash: < 60 seconds (SC-003)
- MCP action execution after approval: < 2 minutes (SC-006)

**Constraints**:
- No secrets in vault markdown files — only `.env` and OS secret manager (FR-019)
- All MCP action scripts must support `DRY_RUN=true` mode (FR-020)
- Offline-capable — vault remains source of truth when Cloud VM unreachable
- Windows Task Scheduler (local scheduling), cron (Cloud VM scheduling)
- 90-day minimum audit log retention in `/Logs/YYYY-MM-DD.json` (FR-021)

**Scale/Scope**: Single user, single vault, ~10 MCP actions/hour max, 4 concurrent
Watcher processes, 24/7 Cloud operation for Platinum tier

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Article | Requirement | Status | Evidence |
|---------|-------------|--------|---------|
| I — Identity & Mandate | Claude = reasoning engine via MCP only | ✅ PASS | FR-012..FR-015; MCP-only execution |
| II — Local-First Sovereignty | Vault = primary memory; no secrets in markdown | ✅ PASS | FR-006, FR-019 |
| III — Deterministic Auditability | All actions logged, traceable, reversible | ✅ PASS | FR-021; /Logs/YYYY-MM-DD.json |
| IV — HITL Supremacy | No irreversible action without file-based approval | ✅ PASS | FR-016, FR-017 |
| V — Ralph Wiggum Doctrine | No premature exit; loop until /Done or ceiling | ✅ PASS | FR-011; 10-iteration ceiling |
| VI — Operational Architecture | Watchers → Vault → Claude → MCP flow | ✅ PASS | FR-001..FR-011 |
| VII — Authority Boundaries | Auto-approve and mandatory approval lists defined | ✅ PASS | FR-016; /Pending_Approval/ |
| VIII — Economic Stewardship | Weekly CEO Briefing + subscription audit | ✅ PASS | FR-022, FR-023 |
| IX — Security & Risk Controls | Env vars, rate limits, degradation protocol | ✅ PASS | FR-004a, FR-019, FR-020 |
| X — Persistence & Execution | Claim-by-move, /In_Progress/, no ghost state | ✅ PASS | FR-026 |
| XI — Cross-Domain Integration | Comms + Accounting + Social + ERP unified | ✅ PASS | FR-015, FR-023 (Gold+) |
| XII — Cloud/Local Separation | Cloud = draft-only, Local = approval authority | ✅ PASS | FR-024..FR-026 (Platinum) |
| XIII — Ethical Constraints | Escalate on ambiguity, emotional, legal, financial | ✅ PASS | FR-016, FR-019a |
| XIV — Non-Negotiable Directives | No fabrication, no HITL bypass, no secret storage | ✅ PASS | FR-013..FR-021 |

**Constitution Check Result: ALL 14 GATES PASS — No violations. Cleared for Phase 0.**

*Post-Phase 1 re-check: No new violations introduced by design decisions. Architecture
adheres to MCP-only execution, claim-by-move concurrency, file-based HITL, and vault
sovereignty principles throughout.*

## Project Structure

### Documentation (this feature)

```text
specs/001-digital-fte-agent/
├── plan.md              # This file (/sp.plan output)
├── research.md          # Phase 0 output
├── data-model.md        # Phase 1 output
├── quickstart.md        # Phase 1 output
├── contracts/           # Phase 1 output
│   ├── vault-file-formats.md
│   ├── mcp-interfaces.md
│   └── watcher-contract.md
└── tasks.md             # Phase 2 output (/sp.tasks — NOT created here)
```

### Source Code (repository root)

```text
src/
├── watchers/
│   ├── base_watcher.py          # Abstract BaseWatcher class
│   ├── gmail_watcher.py         # Gmail OAuth2 polling (every 120s)
│   ├── whatsapp_watcher.py      # Playwright WhatsApp Web (every 30s)
│   ├── filesystem_watcher.py    # Drop-folder watchdog events
│   └── finance_watcher.py       # CSV bank statement parser
├── orchestrator/
│   ├── orchestrator.py          # Master scheduling + folder watching
│   ├── watchdog_process.py      # Process health monitor + restart
│   └── retry_handler.py         # Exponential backoff decorator
├── mcp_servers/
│   ├── email_mcp/               # Gmail send/draft/search (Node.js)
│   │   ├── index.js
│   │   └── package.json
│   ├── browser_mcp/             # Web automation (Node.js + Playwright)
│   │   ├── index.js
│   │   └── package.json
│   ├── calendar_mcp/            # Calendar events (Node.js)
│   │   ├── index.js
│   │   └── package.json
│   └── odoo_mcp/                # Odoo 19 JSON-RPC (Python MCP server)
│       ├── odoo_mcp.py
│       └── pyproject.toml
├── audit/
│   ├── audit_logic.py           # Subscription pattern detection
│   └── ceo_briefing.py          # CEO Briefing generator
└── skills/                      # SKILL.md source (copied to .claude/)
    ├── email-triage.md
    ├── invoice-generator.md
    ├── ceo-briefing.md
    ├── vault-monitor.md
    └── approval-handler.md

vault_template/                  # Obsidian vault initial structure
├── Needs_Action/  (.gitkeep)
├── In_Progress/
│   ├── local/  (.gitkeep)
│   └── cloud/  (.gitkeep)
├── Done/  (.gitkeep)
├── Logs/  (.gitkeep)
├── Plans/  (.gitkeep)
├── Pending_Approval/  (.gitkeep)
├── Approved/  (.gitkeep)
├── Rejected/  (.gitkeep)
├── Briefings/  (.gitkeep)
├── State/  (.gitkeep)
├── Accounting/  (.gitkeep)
├── Updates/  (.gitkeep)
├── Dashboard.md
├── Company_Handbook.md
└── Business_Goals.md

.claude/                         # Agent Skills (Claude Code)
├── email-triage.md
├── invoice-generator.md
├── ceo-briefing.md
├── vault-monitor.md
└── approval-handler.md

tests/
├── unit/
│   ├── test_base_watcher.py
│   ├── test_gmail_watcher.py
│   ├── test_finance_watcher.py
│   └── test_audit_logic.py
├── integration/
│   ├── test_file_watcher_flow.py   # SC-001, SC-002, SC-003
│   ├── test_email_flow.py           # SC-004, SC-005, SC-006
│   └── test_ceo_briefing.py         # SC-007, SC-008, SC-009
└── contract/
    └── test_mcp_interfaces.py       # MCP contract validation

.env.example
pyproject.toml                   # UV Python project (src/ layout)
pm2.config.js                    # PM2 process definitions (all Watchers)
```

**Structure Decision**: Single monorepo with all components co-located. The `vault_template/`
provides the initial Obsidian folder structure; the live vault path is configured via `.env`
(`VAULT_PATH`). MCP servers are Node.js (leveraging the official MCP SDK ecosystem) except
the Odoo MCP which is Python (for direct `httpx` calls to Odoo JSON-RPC). PM2 manages all
Python Watcher processes from `pm2.config.js`.
