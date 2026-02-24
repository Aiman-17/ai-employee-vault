---
type: error
watcher: WhatsAppWatcher
error: AuthExpiredError
status: needs_attention
---

## What happened
WhatsApp monitoring requires Playwright to be installed.

## What to do
Run:
  pip install playwright
  playwright install chromium

## Technical detail
```
Playwright not installed: DLL load failed while importing _greenlet: The specified module could not be found.
```
