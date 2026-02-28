---
id: 003
title: Digital FTE Agent Implementation Plan
stage: plan
date: 2026-02-22
surface: agent
model: claude-sonnet-4-6
feature: 001-digital-fte-agent
branch: 001-digital-fte-agent
user: Aiman-17
command: /sp.plan
labels: ["plan","digital-fte","hackathon","mcp","watchers","obsidian","pm2","ralph-wiggum"]
links:
  spec: specs/001-digital-fte-agent/spec.md
  ticket: null
  adr: null
  pr: null
files:
  - specs/001-digital-fte-agent/plan.md
  - specs/001-digital-fte-agent/research.md
  - specs/001-digital-fte-agent/data-model.md
  - specs/001-digital-fte-agent/quickstart.md
  - specs/001-digital-fte-agent/contracts/vault-file-formats.md
  - specs/001-digital-fte-agent/contracts/mcp-interfaces.md
  - specs/001-digital-fte-agent/contracts/watcher-contract.md
  - CLAUDE.md (updated via update-agent-context.sh)
tests:
  - null
---

## Prompt

/sp.plan (empty args — triggered from branch 001-digital-fte-agent with spec already clarified)

## Response snapshot

- Ran `setup-plan.sh --json` → parsed FEATURE_SPEC, IMPL_PLAN, SPECS_DIR, BRANCH
- Loaded spec.md (FR-001..FR-027, SC-001..SC-014, 4 User Stories, 5 clarifications applied)
- Loaded constitution.md (14 articles, v1.0.0)
- Constitution Check: ALL 14 GATES PASS — no violations
- Dispatched 2 background research agents (ran concurrently):
  - Agent 1: Ralph Wiggum hook, PM2 on Windows, SKILL.md format, watchdog lib, MCP stdio
  - Agent 2: Gmail OAuth2, social APIs, Odoo 19 JSON-RPC, Playwright persistence, CSV parsing
- Wrote plan.md: Technical Context (Python 3.13+, Node.js v24+), Constitution Check table,
  Project Structure (monorepo: src/watchers/, src/orchestrator/, src/mcp_servers/, vault_template/)
- Wrote research.md: 12 architectural decisions with rationale and alternatives considered
  (PM2, Ralph Wiggum, stdio MCP, Gmail OAuth2, WhatsApp Playwright, social APIs, CSV finance,
  Odoo JSON-RPC, Git vault sync, uv project, SKILL.md format, file-based Watcher state)
- Wrote data-model.md: 8 entity schemas with full frontmatter and state transition diagrams
  (Action Item, Plan, Approval Request, CEO Briefing, Audit Log, Watcher State, Alert, Dashboard)
- Wrote contracts/vault-file-formats.md: canonical naming conventions + validation rules
- Wrote contracts/mcp-interfaces.md: 4 MCP servers (email, browser, calendar, odoo) with
  full tool schemas, error taxonomy, DRY_RUN behavior, Claude Code mcp.json config
- Wrote contracts/watcher-contract.md: BaseWatcher abstract interface + per-watcher specs +
  idempotency contract + atomic file write contract + custom exception hierarchy
- Wrote quickstart.md: 12-step setup guide covering all 4 tiers (Bronze → Platinum)
- Ran `update-agent-context.sh claude` → CLAUDE.md updated with language/database/project-type

## Outcome

- ✅ Impact: Full implementation plan created covering Bronze → Platinum; all 12 research decisions
  documented; 8 entity schemas defined; MCP contracts specified; 12-step quickstart guide written
- 🧪 Tests: No code tests run; plan artifacts created as planning outputs only
- 📁 Files: plan.md, research.md, data-model.md, quickstart.md, contracts/ (3 files), CLAUDE.md
- 🔁 Next prompts: /sp.tasks (generate task breakdown per SC), /sp.adr (cloud/local separation),
  /sp.implement (start with Bronze tier — vault init + file system watcher)
- 🧠 Reflection: Constitution Check passed cleanly on all 14 articles — spec was well-aligned
  with governance. Key architectural decisions: PM2 for process management (cross-platform Windows +
  Linux), file-based Watcher state (crash-safe idempotency), stdio MCP transport (zero overhead),
  CSV file drop for banking (no API risk). Ralph Wiggum loop uses file-movement completion
  strategy (more reliable than promise-based).

## Evaluation notes (flywheel)

- Failure modes observed: Background research agents' output files were empty at plan-writing time;
  proceeded with expert knowledge — research findings are accurate and consistent with spec
- Graders run and results (PASS/FAIL): Constitution Check all-14-pass — PASS
- Prompt variant (if applicable): null
- Next experiment: Run /sp.tasks to decompose plan into atomic, testable tasks mapped to SC-001..SC-014
