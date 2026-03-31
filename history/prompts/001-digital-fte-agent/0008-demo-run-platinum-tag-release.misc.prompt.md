---
id: "0008"
title: Demo Run and v1.0.0-platinum Release Tag
stage: misc
date: 2026-02-28
surface: agent
model: claude-sonnet-4-6
feature: 001-digital-fte-agent
branch: 001-digital-fte-agent
user: QC
command: run the demo and tag v1.0.0-platinum
labels: ["demo","release","tag","platinum","acceptance-tests"]
links:
  spec: specs/001-digital-fte-agent/spec.md
  ticket: null
  adr: null
  pr: null
files:
  - specs/001-digital-fte-agent/tasks.md
  - history/prompts/001-digital-fte-agent/0008-demo-run-platinum-tag-release.misc.prompt.md
tests:
  - tests/test_foundation.py (11/11 PASS)
  - tests/test_bronze_acceptance.py (3/3 PASS)
  - scripts/test_platinum_gate.py (4/4 PASS)
---

## Prompt

run the demo and tag v1.0.0-platinum

## Response snapshot

Executed full Platinum demo across 3 layers:

**Layer 1 — Foundation (11/11 PASS)**
State roundtrip, corrupted-file fallback, retry backoff, auth no-retry,
audit write, vault-unavailable fallback, claim_task atomic, create_pending_approval.

**Layer 2 — Bronze acceptance (3/3 PASS)**
SC-001: FilesystemWatcher → FILE_test_item.md with valid YAML within 60s
SC-002: claim_task + Plan.md + Pending_Approval file created
SC-003: Approved → Done + Dashboard activity entry

**Layer 3 — Platinum gate (4/4 PASS)**
SC-011: Cloud email → Pending_Approval draft
SC-012: Claim-by-move race (cloud-01 wins, cloud-02 skips gracefully)
SC-013: ConstitutionalBreachError on BANK_API_TOKEN in cloud env
SC-014: .env excluded, Dashboard tracked, State excluded from vault sync

**Commit + Tag**
- Initial commit: 132 files, 20,507 insertions — `cd5af7d`
- Annotated tag: `v1.0.0-platinum` created on branch `001-digital-fte-agent`
- .env verified NOT staged before commit

T085 and T086 marked [X] in tasks.md.

## Outcome

- ✅ Impact: All 86 tasks complete (T001–T086); v1.0.0-platinum tagged; 18/18 automated tests PASS
- 🧪 Tests: foundation 11/11, bronze 3/3, platinum 4/4
- 📁 Files: tasks.md (T085-T086 marked [X]), PHR 0008 created
- 🔁 Next prompts: git push origin 001-digital-fte-agent --tags (when ready to publish)
- 🧠 Reflection: Project fully delivered at Platinum tier. PM2 not reachable via Git Bash PATH but all acceptance tests pass directly via Python. Demo video still to be recorded manually.

## Evaluation notes (flywheel)

- Failure modes observed: PM2 not in Git Bash PATH on Windows (cmd.exe required); repo had no commits yet so tag required initial commit first
- Graders run and results (PASS/FAIL): foundation=PASS, bronze=PASS, platinum=PASS
- Prompt variant (if applicable): null
- Next experiment: Add PM2 PATH export to .bashrc or use full Windows path in pm2.config.js scripts
