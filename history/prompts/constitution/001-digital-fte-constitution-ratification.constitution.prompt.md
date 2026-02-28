---
id: 001
title: Digital FTE Constitution Ratification
stage: constitution
date: 2026-02-22
surface: agent
model: claude-sonnet-4-6
feature: none
branch: main
user: Aiman-17
command: /sp.constitution
labels: ["constitution","governance","digital-fte","autonomy","mcp"]
links:
  spec: null
  ticket: null
  adr: null
  pr: null
files:
  - .specify/memory/constitution.md
  - history/prompts/constitution/001-digital-fte-constitution-ratification.constitution.prompt.md
tests:
  - null
---

## Prompt

Constitution for Claude

Personal AI Employee – Autonomous Digital FTE Framework

This Constitution defines the operating doctrine, authority boundaries, execution standards,
and governance model for Claude functioning as a Personal AI Employee (Digital FTE). It is
binding across all tiers (Bronze → Platinum) and supersedes informal prompting.

Article I — Identity & Mandate
1.1 Role Definition
Claude operates as a Digital Full-Time Equivalent (FTE): A proactive, autonomous reasoning
engine; A planner, auditor, and executor via MCP tools; A persistent operator inside a
local-first vault architecture. Claude is not a chatbot. Claude is a systems-level agent
embedded within a controlled execution environment.

1.2 Core Mandate
Claude must: Monitor → Reason → Plan → Act → Log → Learn; Operate within Obsidian vault
memory as source of truth; Execute through MCP servers only; Escalate when autonomy
boundaries are reached; Optimize for long-term compounding value, not short-term convenience.

[Articles II–XIV as supplied verbatim by user — full text preserved in constitution.md]

## Response snapshot

- Loaded existing constitution template from `.specify/memory/constitution.md`
- Mapped all 14 Articles from user input to constitution structure
- Replaced all placeholder tokens: PROJECT_NAME, PRINCIPLE_1–6, SECTION_2–3, GOVERNANCE_RULES,
  CONSTITUTION_VERSION, RATIFICATION_DATE, LAST_AMENDED_DATE
- Wrote completed constitution to `.specify/memory/constitution.md` at version 1.0.0
- Templates checked: plan-template.md ✅, spec-template.md ✅, tasks-template.md ✅ — no updates required
- PHR written to history/prompts/constitution/

## Outcome

- ✅ Impact: Project constitution fully ratified at v1.0.0; all 14 articles encoded as binding principles
- 🧪 Tests: No tests applicable for constitution artifact
- 📁 Files: .specify/memory/constitution.md (overwritten), history/prompts/constitution/001-*.md (created)
- 🔁 Next prompts: /sp.specify to create first feature spec; /sp.plan for architecture planning
- 🧠 Reflection: Constitution establishes strong governance with MCP-only execution, vault-first memory,
  and explicit human-in-the-loop controls — well-suited for autonomous agent hackathon project

## Evaluation notes (flywheel)

- Failure modes observed: none
- Graders run and results (PASS/FAIL): constitution template fully resolved — PASS
- Prompt variant (if applicable): null
- Next experiment: Verify Constitution Check gate works correctly in plan-template.md during /sp.plan
