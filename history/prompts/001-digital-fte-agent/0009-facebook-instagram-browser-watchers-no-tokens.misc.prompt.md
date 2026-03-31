---
id: "0009"
title: Facebook Instagram Browser Watchers No Tokens
stage: misc
date: 2026-02-28
surface: agent
model: claude-sonnet-4-6
feature: 001-digital-fte-agent
branch: 001-digital-fte-agent
user: QC
command: python watchers like whats app for facebook and insta without need access tokens?
labels: ["facebook","instagram","playwright","browser-watcher","no-token","dm-monitoring"]
links:
  spec: specs/001-digital-fte-agent/spec.md
  ticket: null
  adr: null
  pr: null
files:
  - src/watchers/facebook_watcher.py
  - src/watchers/instagram_watcher.py
  - scripts/setup_facebook_session.py
  - scripts/setup_instagram_session.py
  - src/orchestrator/main.py
  - pm2.config.js
  - .env.example
tests:
  - smoke: FacebookWatcher() import OK
  - smoke: InstagramWatcher() import OK
---

## Prompt

python watchers like whats app for facebook and insta without need access tokens?
because facebook access tokens not generating

## Response snapshot

Built two Playwright browser-based watchers that require NO access tokens or
developer app registration — same approach as WhatsApp watcher (persistent
Chromium session, one-time manual login):

**FacebookWatcher** (`src/watchers/facebook_watcher.py`)
- Navigates to https://www.facebook.com/messages/ using saved session
- Login detection: checks URL + `input#email` presence → SessionInvalidError
- Primary strategy: finds conversation elements with aria-label containing "unread"
- Fallback strategy: JS evaluation of font-weight >= 700 (bold = unread sender)
- Keyword filter → writes FACEBOOK_<sender>_<ts>.md to Needs_Action/
- check_interval: 60s, headless when AGENT_MODE=cloud

**InstagramWatcher** (`src/watchers/instagram_watcher.py`)
- Navigates to https://www.instagram.com/direct/inbox/ using saved session
- Login detection: checks `/accounts/login` in URL + login form selector
- Dismisses cookie/notification popups automatically
- Primary strategy: role="listbox" > role="option" with [aria-label*="unread"] or child dot
- Fallback strategy: same JS bold font-weight evaluation
- Keyword filter → writes INSTAGRAM_<sender>_<ts>.md to Needs_Action/
- check_interval: 60s

**Setup scripts** (run once, visible browser):
- `scripts/setup_facebook_session.py` → FACEBOOK_SESSION_PATH
- `scripts/setup_instagram_session.py` → INSTAGRAM_SESSION_PATH (also verifies DM inbox)

**Registered** in main.py (guarded by session path env vars) and pm2.config.js.
Smoke test: both import and instantiate cleanly.

## Outcome

- ✅ Impact: FB + IG DM monitoring without any API token or developer app
- 🧪 Tests: import smoke test PASS for both watchers
- 📁 Files: 7 files created/modified
- 🔁 Next prompts: run setup scripts, set session paths in .env, test with real DMs
- 🧠 Reflection: Selector strategy mirrors WhatsApp watcher. Facebook/IG update their UI frequently — aria-label selectors are more stable than class names. Bold font-weight JS fallback adds resilience.

## Evaluation notes (flywheel)

- Failure modes observed: FB/IG obfuscate CSS class names; solution is aria-label + role selectors + JS bold detection fallback
- Graders run and results (PASS/FAIL): import smoke test = PASS
- Prompt variant (if applicable): null
- Next experiment: Add `page.wait_for_load_state("networkidle")` before scraping for more reliable detection
