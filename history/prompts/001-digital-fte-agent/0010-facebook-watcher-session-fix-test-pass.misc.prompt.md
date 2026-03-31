---
id: "0010"
title: Facebook Watcher Session Fix and Test Pass
stage: misc
date: 2026-02-28
surface: agent
model: claude-sonnet-4-6
feature: 001-digital-fte-agent
branch: 001-digital-fte-agent
user: QC
command: run setup_facebook_session.py first / test facebook watcher
labels: ["facebook","playwright","session","selector-fix","test-pass"]
links:
  spec: specs/001-digital-fte-agent/spec.md
  ticket: null
  adr: null
  pr: null
files:
  - scripts/setup_facebook_session.py
  - scripts/setup_instagram_session.py
  - src/watchers/facebook_watcher.py
tests:
  - check_for_updates() single-cycle: PASS (0 unread keyword matches)
---

## Prompt

run setup_facebook_session.py first
test facebook watcher

## Response snapshot

**Bug fixed**: `[role="main"]` in `_LOADED_SEL` matched the Facebook *login* page,
causing the setup script to immediately detect "Messenger loaded" before the user
could log in (window closed in 2 seconds without login).

**Fix**: Replaced `[role="main"]` with Messenger-specific selectors
`[aria-label="Messenger"], [aria-label="Chats"], [aria-label="New message"]`
in both setup script and watcher.

Also removed `input("Press Enter...")` from setup_facebook_session.py and
setup_instagram_session.py — Claude Code bash tool has no interactive stdin.

**Test result**: `check_for_updates()` ran successfully, loaded Messenger with
saved session (headless), returned 0 items (no keyword-matching unread messages).

## Outcome

- ✅ Impact: FacebookWatcher fully functional — session saved, headless check passes
- 🧪 Tests: single check_for_updates() cycle PASS
- 📁 Files: setup_facebook_session.py, setup_instagram_session.py, facebook_watcher.py
- 🔁 Next prompts: test instagram watcher, send test FB message with keyword to verify detection
- 🧠 Reflection: [role="main"] is too generic — always use feature-specific aria-labels for login vs loaded detection

## Evaluation notes (flywheel)

- Failure modes observed: [role="main"] present on both login and logged-in page → premature "success" detection
- Graders run and results (PASS/FAIL): facebook check_for_updates = PASS
- Prompt variant (if applicable): null
- Next experiment: Add page.wait_for_load_state("networkidle") before scraping for more reliable DOM readiness
