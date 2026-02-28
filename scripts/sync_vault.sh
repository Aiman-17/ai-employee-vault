#!/usr/bin/env bash
# =============================================================================
# scripts/sync_vault.sh — Sync the Obsidian vault to the Git remote.
#
# Security (Constitution Article IX):
#   - Secrets, State/*.json, WhatsApp sessions excluded by vault .gitignore
#   - Never syncs .env or credential files
#   - Cloud writes to markdown only; secrets stay on respective machines
#
# Usage:
#   VAULT_PATH=/path/to/vault bash scripts/sync_vault.sh
#
# Scheduled via orchestrator every VAULT_SYNC_INTERVAL_MINUTES (default 15).
# =============================================================================

set -euo pipefail

VAULT_PATH="${VAULT_PATH:-$HOME/Documents/AI_Employee_Vault}"
AGENT_ID="${CLOUD_AGENT_ID:-local}"

# ── Pre-flight checks ─────────────────────────────────────────────────────────

if [ ! -d "$VAULT_PATH" ]; then
  echo "[sync_vault] ERROR: Vault directory not found: $VAULT_PATH"
  echo "  Run scripts/setup_vault.py to create the vault."
  exit 1
fi

if [ ! -d "$VAULT_PATH/.git" ]; then
  echo "[sync_vault] ERROR: $VAULT_PATH is not a git repository."
  echo "  Initialise with:"
  echo "    cd \"$VAULT_PATH\""
  echo "    git init"
  echo "    git remote add origin \$VAULT_GIT_REMOTE"
  echo "    git add -A && git commit -m 'initial vault'"
  echo "    git push -u origin main"
  exit 1
fi

# ── Sync ──────────────────────────────────────────────────────────────────────

cd "$VAULT_PATH"
echo "[sync_vault] Syncing vault at $VAULT_PATH (agent: $AGENT_ID)..."

# Pull remote changes — prefer remote on conflict (Cloud is drafter, Local is authority)
git fetch origin 2>/dev/null || true

# Try merging; if conflicts exist, prefer remote (theirs) and continue
if git merge --ff-only origin/main 2>/dev/null || git merge --ff-only origin/master 2>/dev/null; then
  echo "[sync_vault] Pulled remote changes."
else
  # Non-fast-forward: use theirs strategy to prefer remote
  git merge -X theirs origin/main 2>/dev/null \
    || git merge -X theirs origin/master 2>/dev/null \
    || true
fi

# Stage all tracked and new markdown files
git add -A

# Commit only when there are staged changes
if ! git diff --cached --quiet; then
  TIMESTAMP=$(date -u +%Y-%m-%dT%H:%M:%SZ 2>/dev/null || python3 -c "from datetime import datetime, timezone; print(datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ'))")
  git commit -m "vault sync $TIMESTAMP [agent:$AGENT_ID]"
  git push origin HEAD
  echo "[sync_vault] Vault synced and pushed."
else
  echo "[sync_vault] Nothing to sync — vault is up to date."
fi
