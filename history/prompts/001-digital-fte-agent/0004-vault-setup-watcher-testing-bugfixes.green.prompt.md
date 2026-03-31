---
id: "0004"
title: Vault Setup Watcher Testing Bugfixes
stage: green
date: 2026-02-24
surface: agent
model: claude-sonnet-4-6
feature: 001-digital-fte-agent
branch: 001-digital-fte-agent
user: QC
command: "open the vault in obsidian and test the filesystem watcher"
labels: ["vault-setup","filesystem-watcher","bugfix","obsidian","testing","bronze-tier"]
links:
  spec: specs/001-digital-fte-agent/spec.md
  ticket: null
  adr: null
  pr: null
files:
  - .env
  - scripts/setup_vault.py
  - src/watchers/filesystem_watcher.py
  - src/watchers/base_watcher.py
  - pyproject.toml
  - vault/C:/Users/QC/Documents/AI_Employee_Vault/Dashboard.md
  - vault/C:/Users/QC/Documents/AI_Employee_Vault/Company_Handbook.md
  - vault/C:/Users/QC/Documents/AI_Employee_Vault/.obsidian/app.json
  - vault/C:/Users/QC/Documents/AI_Employee_Vault/.obsidian/workspace.json
tests:
  - tests/test_gold_acceptance.py (10/10 PASSED)
  - FilesystemWatcher end-to-end drop test (PASSED — Needs_Action/ contains only .md)
---

## Prompt

1. "open the vault in obsidian and test the filesystem watcher"
2. "FILE_Invoice_Client_ABC_Feb2026.md — This file saved with pdf extension not md"
3. "now create the PHR for this session"

Also ran Gold tier acceptance tests: "run the gold acceptance tests"

## Response snapshot

**Gold acceptance tests (10/10 PASSED):**
- Fixed pytest discovery: added `python_classes = ["Test*", "*Test"]` to `pyproject.toml` so classes named `SC007CEOBriefingTest` / `SC008SC009RalphWiggumTest` are collected.

**Vault setup:**
- Updated `.env`: set `VAULT_PATH=C:/Users/QC/Documents/AI_Employee_Vault`, `FILE_DROP_PATH=...Vault/Inbox`, `GMAIL_CREDENTIALS_PATH`, `WHATSAPP_SESSION_PATH` to real paths.
- Ran `scripts/setup_vault.py` → copied 4 files (Dashboard.md, Company_Handbook.md, Business_Goals.md, Accounting/Current_Month.md) and created 13 vault folders (Needs_Action/, Done/, Inbox/, In_Progress/, Approved/, Rejected/, Pending_Approval/, Briefings/, Plans/, Invoices/, Logs/, State/, Updates/).
- Fixed `setup_vault.py` Unicode bug: `→` arrow in print statement caused `UnicodeEncodeError` on Windows cp1252 — replaced with `->`.
- Created `.obsidian/app.json` and `.obsidian/workspace.json` to register vault and set Dashboard.md as default open tab.
- Launched Obsidian from `C:\Users\QC\Desktop\digital_FTE\Obsidian\Obsidian.exe`.

**FilesystemWatcher bug 1 — PDF copied into Needs_Action/ top level:**
- Root cause: `create_action_file()` called `shutil.copy2(item, dest)` where `dest = self.needs_action / f"FILE_{item.name}"`, placing the raw file directly alongside the `.md` card.
- Fix: removed `shutil.copy2` entirely. Raw file stays in `Inbox/`; action card references it via `original_path` in YAML frontmatter and `**Location**: {item}` in body. `Needs_Action/` now contains only `.md` files.
- Also removed unused `shutil` import and `VaultLockError` import.

**FilesystemWatcher bug 2 — DuplicateItemError crashing tick:**
- Root cause: `base_watcher._tick()` raised `DuplicateItemError` when an already-seen item appeared, which bubbled up to the `run()` generic exception handler and silently dropped all items in that tick.
- Fix: changed `raise DuplicateItemError(...)` to `logger.debug(...); continue` — duplicates are silently skipped, processing continues for other items.

**Stale background process diagnosis:**
- Multiple `python -m src.watchers.filesystem_watcher &` background jobs from earlier test runs persisted as orphan processes (PIDs 10880, 16820, 8356), each with a different in-memory version of the code.
- Symptoms: PDF appeared in `Needs_Action/` despite source edits; `__pycache__` clearing had no effect.
- Diagnosed via: second watchdog Observer on `Needs_Action/` logged 3 separate `created` events for the same file from 3 different processes.
- Fix: `powershell -Command "Stop-Process -Id 10880,16820,8356 -Force"` (bash `taskkill` was silently failing).
- Lesson: never start watchers with `&` in tests; always use foreground or track PIDs for cleanup.

**Final clean test result:**
```
Needs_Action/ ===
  [md OK]  FILE_Invoice_FINAL_1771860902.md    ← only .md, no PDF
```

## Outcome

- ✅ Impact: Obsidian vault live at `C:\Users\QC\Documents\AI_Employee_Vault` with all 13 folders + Dashboard.md + Company_Handbook.md; FilesystemWatcher tested end-to-end; Bronze tier fully operational
- 🧪 Tests: Gold acceptance tests 10/10 PASS; FilesystemWatcher drop-to-card test PASS
- 📁 Files: `.env`, `setup_vault.py`, `filesystem_watcher.py`, `base_watcher.py`, `pyproject.toml`, `.obsidian/` config
- 🔁 Next prompts: Gmail OAuth2 setup (`python scripts/setup_gmail_auth.py`), WhatsApp QR scan (`playwright install chromium` then `python -m src.watchers.whatsapp_watcher`), LinkedIn watcher implementation
- 🧠 Reflection: stale background processes are the most insidious testing footgun on Windows — PowerShell `Stop-Process` is the only reliable kill method; always verify no watchers are running before testing with `wmic process where "name='python.exe'" get ProcessId,CommandLine`

## Evaluation notes (flywheel)

- Failure modes observed: (1) stale pyc bytecode masked by stale processes; (2) DuplicateItemError was raise not continue — silent tick failure; (3) Windows cp1252 rejects Unicode arrows/checkmarks in print statements
- Graders run and results (PASS/FAIL): Gold acceptance 10/10 PASS; FilesystemWatcher integration PASS (after killing ghost processes)
- Prompt variant (if applicable): null
- Next experiment (smallest change to try): add `PYTHONIOENCODING=utf-8` to `.env` or set it in `pm2.config.js` env block to prevent cp1252 encoding errors across all watcher processes
