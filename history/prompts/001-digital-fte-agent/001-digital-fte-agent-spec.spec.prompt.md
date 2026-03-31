---
id: 001
title: Digital FTE Agent Specification
stage: spec
date: 2026-02-22
surface: agent
model: claude-sonnet-4-6
feature: 001-digital-fte-agent
branch: 001-digital-fte-agent
user: Aiman-17
command: /sp.specify
labels: ["spec","digital-fte","hackathon","obsidian","mcp","watchers","hitl","claude-code"]
links:
  spec: specs/001-digital-fte-agent/spec.md
  ticket: null
  adr: null
  pr: null
files:
  - specs/001-digital-fte-agent/spec.md
  - specs/001-digital-fte-agent/checklists/requirements.md
  - history/prompts/001-digital-fte-agent/001-digital-fte-agent-spec.spec.prompt.md
tests:
  - null
---

## Prompt

Personal AI Employee Hackathon 0: Building Autonomous FTEs (Full-Time Equivalent) in 2026
Tagline: Your life and business on autopilot. Local-first, agent-driven, human-in-the-loop.

[Full hackathon specification document provided — covers architecture, 4 tiers
(Bronze/Silver/Gold/Platinum), tech stack (Claude Code + Obsidian + Python Watchers
+ MCP servers), watcher patterns, Ralph Wiggum loop, business audit/CEO Briefing,
security architecture, error recovery, Odoo integration, cloud/local separation, and
judging criteria. Target tier: Platinum.]

## Response snapshot

- Generated branch name: `digital-fte-agent` → executed `create-new-feature.sh`
  → branch `001-digital-fte-agent` created, SPEC_FILE at
  `specs/001-digital-fte-agent/spec.md`
- Wrote full spec with 4 User Stories (one per hackathon tier, P1–P4)
- FR-001–FR-027 covering: Perception (Watchers), Vault, Reasoning, Action (MCP),
  HITL, Security, Business Audit, Cloud/Local Separation, Agent Skills
- SC-001–SC-014 measurable outcomes across all 4 tiers
- Key entities: Action Item, Plan, Approval Request, CEO Briefing, Audit Log,
  Agent Skill, Watcher State
- Edge cases: duplicate ingestion, vault lock, API expiry, WA session loss,
  banking timeout, Ralph loop ceiling, approval expiry, Cloud VM unreachable
- Quality checklist: all items pass on first validation

## Outcome

- ✅ Impact: Full hackathon spec created covering Bronze → Platinum tiers with
  27 functional requirements and 14 success criteria
- 🧪 Tests: No code tests applicable; checklist validation PASS
- 📁 Files: specs/001-digital-fte-agent/spec.md, checklists/requirements.md
- 🔁 Next prompts: /sp.plan (architecture planning), /sp.clarify (optional
  refinements), /sp.adr (cloud/local separation decision)
- 🧠 Reflection: Spec cleanly separates the 4 hackathon tiers as P1–P4 user
  stories; each is independently testable and maps to judging criteria
  (Functionality 30%, Innovation 25%, Practicality 20%, Security 15%, Docs 10%)

## Evaluation notes (flywheel)

- Failure modes observed: none
- Graders run and results (PASS/FAIL): quality checklist all-pass — PASS
- Prompt variant (if applicable): null
- Next experiment: Run /sp.plan to generate architecture decisions; expect ADR
  suggestion for cloud/local vault sync model
