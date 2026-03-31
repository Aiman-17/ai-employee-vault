---
id: "0006"
title: "whatsapp-selector-fix-watcher-tests-pass"
stage: misc
date: 2026-02-24
surface: agent
model: claude-sonnet-4-6
feature: 001-digital-fte-agent
branch: main
user: QC
command: /sp.implement
labels: ["whatsapp", "watcher", "selector-fix", "linkedin", "twitter", "testing"]
links:
  spec: specs/001-digital-fte-agent/spec.md
  ticket: null
  adr: null
  pr: null
files:
  - src/watchers/whatsapp_watcher.py
  - scripts/setup_whatsapp_session.py
  - .env (LINKEDIN_AUTHOR_URN added)
tests:
  - scripts/_wa_watcher_test.py (WhatsApp watcher PASS)
  - LinkedIn DRY_RUN test (PASS)
---

## Prompt

Session resumed. User scanned WhatsApp QR code. Continue testing all watchers. User message: "Already scan the whatsapp qr" / "whats app open on browser" / "after loading chats chromium windows closing" / "Never expose keys in prompts"

## Response snapshot

WhatsApp watcher was failing with `[data-testid="chat-list"]` timeout. Diagnosed that WhatsApp Web updated their UI -- the selector no longer exists. Confirmed working selector is `[aria-label="Chat list"]` via Playwright inspection. Updated both whatsapp_watcher.py and setup_whatsapp_session.py with the corrected selector (with old testid as fallback). Added LINKEDIN_AUTHOR_URN=urn:li:person:_N-aqDiBFR to .env. Tested all watchers.

## Outcome

- Impact: All 5 watchers now pass. WhatsApp selector bug fixed. LinkedIn AUTHOR_URN configured. Twitter blocked on 4 missing OAuth 1.0a keys.
- Tests: WhatsApp PASS, LinkedIn DRY_RUN PASS, Gmail PASS, Finance PASS, Filesystem PASS
- Files: src/watchers/whatsapp_watcher.py, scripts/setup_whatsapp_session.py, .env
- Next prompts: Add Twitter OAuth keys (API_KEY, API_SECRET, ACCESS_TOKEN, ACCESS_TOKEN_SECRET) then test Twitter poster; test LinkedIn live post (DRY_RUN=false); initialize vault Git remote
- Reflection: WhatsApp Web periodically changes data-testid selectors -- aria-label selectors are more stable as they're accessibility attributes that change less frequently

## Evaluation notes (flywheel)

- Failure modes observed: `[data-testid="chat-list"]` removed in WhatsApp Web UI update; concurrent Playwright sessions lock the profile dir causing goto timeout; never expose credential values in tool calls
- Graders run and results (PASS/FAIL): _wa_watcher_test.py -- PASS (0 urgent messages)
- Prompt variant (if applicable): null
- Next experiment: Use aria-label selectors as primary, data-testid as fallback for all WhatsApp selectors
