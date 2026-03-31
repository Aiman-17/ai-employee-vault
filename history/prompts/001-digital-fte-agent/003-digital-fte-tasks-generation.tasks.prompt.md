---
id: 003
title: Digital FTE Tasks Generation
stage: tasks
date: 2026-02-22
surface: agent
model: claude-sonnet-4-6
feature: 001-digital-fte-agent
branch: 001-digital-fte-agent
user: Aiman-17
command: /sp.tasks
labels: ["tasks","digital-fte","hackathon","obsidian","mcp","watchers","hitl","bronze","silver","gold","platinum"]
links:
  spec: specs/001-digital-fte-agent/spec.md
  ticket: null
  adr: null
  pr: null
files:
  - specs/001-digital-fte-agent/tasks.md
tests:
  - null
---

## Prompt

/sp.tasks (no additional text — user said "go ahead" to proceed)

Context: User invoked /sp.tasks after completing the spec and plan phases for the Digital FTE Agent hackathon project (Panaversity Hackathon 0: Building Autonomous FTEs). All design documents were available: plan.md, spec.md, data-model.md, research.md, quickstart.md, contracts/watcher-contract.md, contracts/mcp-interfaces.md.

## Response snapshot

- Ran check-prerequisites.sh to get FEATURE_DIR = `specs/001-digital-fte-agent/`
- Loaded all design documents: plan.md (tech stack, UV project, project structure), spec.md (4 user stories P1–P4 = Bronze–Platinum), data-model.md (8 entities), research.md (12 architectural decisions), quickstart.md (acceptance tests), contracts/ (BaseWatcher interface + 4 MCP server tools)
- Generated comprehensive `specs/001-digital-fte-agent/tasks.md` with:
  - **Phase 1: Setup** (T001–T013): UV project, vault template, MCP skeletons, PM2, .env.example, .gitignore
  - **Phase 2: Foundational** (T014–T023): exceptions, retry_handler, state_manager, audit_logger, BaseWatcher ABC, vault_utils, dry_run, orchestrator skeleton, watchdog
  - **Phase 3: US1 Bronze** (T024–T032): FilesystemWatcher, approval_handler, Dashboard update, vault-monitor skill, approval-handler skill, PM2 entries, SC-001/SC-002/SC-003 acceptance tests
  - **Phase 4: US2 Silver** (T033–T048): GmailWatcher, WhatsAppWatcher, FinanceWatcher, email-mcp (Node.js), calendar-mcp, HITL email integration, audit_logic.py, email-triage skill, invoice-generator skill, LinkedIn poster, SC-004/SC-005 tests
  - **Phase 5: US3 Gold** (T049–T065): Ralph Wiggum Stop hook, CEO Briefing generator, Odoo MCP (Python FastMCP), browser-mcp (Node.js+Playwright), Facebook/Instagram/Twitter posters, subscription audit integration, error degradation handlers, SC-007/SC-008/SC-009 tests
  - **Phase 6: US4 Platinum** (T066–T081): pm2.cloud.config.js, cloud_constraints.py, AGENT_MODE separation, Git vault sync, claim-by-move enforcement, Dashboard single-writer lock, Cloud update merge, Odoo Docker setup script, Cloud VM bootstrap script, Platinum gate acceptance test script, SC-011–SC-014 tests
  - **Phase 7: Polish** (T082–T086): README, security audit, final test run, demo video, git tag
- Total: 86 tasks (T001–T086)
- All tasks follow required format: `- [ ] TXXX [P?] [USn?] Description with exact file path`
- Dependency graph, parallel execution examples, incremental delivery strategy included
- PHR created at `history/prompts/001-digital-fte-agent/003-digital-fte-tasks-generation.tasks.prompt.md`

## Outcome

- ✅ Impact: 86 tasks generated across 7 phases covering Bronze → Platinum tier delivery; each phase independently testable; tasks map directly to plan.md file structure with exact paths
- 🧪 Tests: No automated test suite (not explicitly requested); SC-* acceptance tests included as task verification gates per quickstart.md; T023 foundation smoke test included
- 📁 Files: specs/001-digital-fte-agent/tasks.md (created)
- 🔁 Next prompts: /sp.implement (execute tasks), /sp.adr cloud-local-agent-separation (document Platinum architecture decision), /sp.git.commit_pr (commit current state to branch)
- 🧠 Reflection: Tasks cleanly organized by hackathon tier (Bronze=US1, Silver=US2, Gold=US3, Platinum=US4); hackathon priority ordering added in Implementation Strategy section to help user time-box correctly given judging weights (Functionality 30%, Innovation 25%); Ralph Wiggum Stop hook and CEO Briefing flagged as highest-impact items for innovation score

## Evaluation notes (flywheel)

- Failure modes observed: none — all design documents loaded successfully; no missing paths or contradictions between contracts and plan.md
- Graders run and results (PASS/FAIL): tasks format validated against template rules — PASS; all tasks have ID, checkbox, description with file path; [US] labels present for story phases; [P] markers on parallelizable tasks — PASS
- Prompt variant (if applicable): null
- Next experiment: Run /sp.implement to begin Bronze tier (T001–T032); verify SC-001 acceptance test passes within 60 seconds of file drop
