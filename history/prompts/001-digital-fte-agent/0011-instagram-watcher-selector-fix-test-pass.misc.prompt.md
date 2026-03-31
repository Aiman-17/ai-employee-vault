---
id: "0011"
title: Instagram Watcher Selector Fix and Test Pass
stage: misc
date: 2026-02-28
surface: agent
model: claude-sonnet-4-6
feature: 001-digital-fte-agent
branch: 001-digital-fte-agent
user: QC
command: test instagram watcher
labels: ["instagram","playwright","selector-fix","dom-inspection","test-pass"]
links:
  spec: specs/001-digital-fte-agent/spec.md
  ticket: null
  adr: null
  pr: null
files:
  - src/watchers/instagram_watcher.py
  - scripts/setup_instagram_session.py
tests:
  - check_for_updates() single-cycle: PASS (1 unread detected via title, 0 keyword matches)
---

## Prompt

test instagram watcher

## Response snapshot

**Problem**: Original selectors `[aria-label="Direct messaging"]`, `[role="listbox"]` timed
out — Instagram changed its DM inbox UI.

**DOM inspection findings** (2026-02-28):
- Correct loaded selector: `[aria-label="Thread list"]` (role="navigation")
- Unread count: page title prefix `(1) Instagram • Messages`
- Thread items: no `<a href="/direct/t/">` tags; no role="listitem"; fully virtualized list
- Unread detection: bold font-weight (>= 700) leaf nodes = unread sender names
- UI strings to filter out: "Messages", "Requests", "Search", etc.

**Rewrote watcher** with:
1. `_THREAD_LIST_SEL = '[aria-label="Thread list"]'` as loaded indicator
2. Title-based unread count check → early return if 0 (skip DOM scan)
3. `_FIND_BOLD_JS` — JS that walks all leaf nodes, finds bold ones, walks up DOM
   to get container with sender + preview lines
4. `_filter_items()` — removes known UI strings, filters by keywords

**Test result**:
- Title detected: `(1) Instagram • Messages` → 1 unread
- Bold senders found: `aish_d75`, `Apa Fer Milaange`
- Keyword check: neither matches business keywords → 0 items returned (correct)

## Outcome

- ✅ Impact: InstagramWatcher fully functional with correct DOM-based detection
- 🧪 Tests: check_for_updates() PASS — detected 1 unread, 0 keyword matches (expected)
- 📁 Files: instagram_watcher.py rewritten, setup_instagram_session.py (input() removed)
- 🔁 Next prompts: send test IG DM with keyword to verify card creation
- 🧠 Reflection: Instagram's virtualized list has no semantic role/aria on thread items — title-based unread count + bold font-weight is the most stable detection strategy

## Evaluation notes (flywheel)

- Failure modes observed: [role="listbox"] gone from IG DM inbox in current UI; networkidle never fires on IG (SPA with continuous polling)
- Graders run and results (PASS/FAIL): check_for_updates = PASS
- Prompt variant (if applicable): null
- Next experiment: Also check [aria-label*="unread"] on thread containers as secondary confirmation
