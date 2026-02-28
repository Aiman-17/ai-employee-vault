#!/usr/bin/env bash
# =============================================================================
# scripts/setup_cloud_agent.sh — Bootstrap script for Cloud VM agent
#
# Run on a fresh Ubuntu 22.04 / Debian cloud VM (Oracle Cloud, AWS, GCP):
#   curl -sSL https://raw.githubusercontent.com/<user>/digital-fte/main/scripts/setup_cloud_agent.sh | bash
#
# Or after cloning the repo:
#   bash scripts/setup_cloud_agent.sh
#
# What this does:
#   1. Installs system dependencies (Python 3.13, Node.js v24, PM2)
#   2. Installs UV package manager
#   3. Installs Python + Node project dependencies
#   4. Creates .env from .env.cloud.example if not present
#   5. Validates AGENT_MODE=cloud in .env
#   6. Starts PM2 with pm2.cloud.config.js
# =============================================================================

set -euo pipefail

REPO_DIR="${1:-$(pwd)}"
LOG_PREFIX="[setup_cloud_agent]"

info()  { echo "$LOG_PREFIX INFO:  $*"; }
warn()  { echo "$LOG_PREFIX WARN:  $*" >&2; }
error() { echo "$LOG_PREFIX ERROR: $*" >&2; exit 1; }

# ── 1. System packages ────────────────────────────────────────────────────────

info "Installing system dependencies..."
sudo apt-get update -qq
sudo apt-get install -y \
  curl wget git build-essential \
  libssl-dev libffi-dev zlib1g-dev libbz2-dev \
  libreadline-dev libsqlite3-dev libncurses5-dev \
  libgdbm-dev libnss3-dev liblzma-dev uuid-dev \
  xvfb xauth xfonts-base  # for headless Chromium if needed

# ── 2. Python 3.13 (via deadsnakes PPA) ──────────────────────────────────────

if ! command -v python3.13 &>/dev/null; then
  info "Installing Python 3.13..."
  sudo add-apt-repository -y ppa:deadsnakes/ppa
  sudo apt-get install -y python3.13 python3.13-venv python3.13-dev
else
  info "Python 3.13 already installed: $(python3.13 --version)"
fi

# ── 3. Node.js v24 LTS ───────────────────────────────────────────────────────

if ! command -v node &>/dev/null || [[ "$(node -v)" != v24* ]]; then
  info "Installing Node.js v24..."
  curl -fsSL https://deb.nodesource.com/setup_24.x | sudo -E bash -
  sudo apt-get install -y nodejs
else
  info "Node.js already installed: $(node -v)"
fi

# ── 4. PM2 ────────────────────────────────────────────────────────────────────

if ! command -v pm2 &>/dev/null; then
  info "Installing PM2..."
  sudo npm install -g pm2
else
  info "PM2 already installed: $(pm2 -v)"
fi

# ── 5. UV Python package manager ─────────────────────────────────────────────

if ! command -v uv &>/dev/null; then
  info "Installing UV..."
  curl -LsSf https://astral.sh/uv/install.sh | sh
  export PATH="$HOME/.local/bin:$PATH"
else
  info "UV already installed: $(uv --version)"
fi

# ── 6. Python dependencies ────────────────────────────────────────────────────

cd "$REPO_DIR"
info "Installing Python dependencies with UV..."
uv sync

# Install Playwright + Chromium headless (for WhatsApp — not used on Cloud
# but installed so imports don't fail)
uv run playwright install chromium --with-deps || warn "Playwright install failed (optional on Cloud)"

# ── 7. Node.js MCP server dependencies ───────────────────────────────────────

for mcp_dir in src/mcp_servers/email_mcp src/mcp_servers/calendar_mcp src/mcp_servers/browser_mcp; do
  if [ -f "$REPO_DIR/$mcp_dir/package.json" ]; then
    info "Installing Node.js deps for $mcp_dir..."
    npm install --prefix "$REPO_DIR/$mcp_dir"
  fi
done

# ── 8. Environment setup ──────────────────────────────────────────────────────

if [ ! -f "$REPO_DIR/.env" ]; then
  info "Creating .env from .env.cloud.example..."
  cp "$REPO_DIR/.env.cloud.example" "$REPO_DIR/.env"
  warn "IMPORTANT: Edit $REPO_DIR/.env and fill in real credentials before starting PM2."
  warn "  Required: GMAIL_CLIENT_ID, GMAIL_CLIENT_SECRET, VAULT_GIT_REMOTE, ODOO_API_KEY"
else
  info ".env already exists — skipping template copy."
fi

# Validate AGENT_MODE=cloud
if grep -q "^AGENT_MODE=cloud" "$REPO_DIR/.env" 2>/dev/null; then
  info "AGENT_MODE=cloud confirmed in .env"
else
  warn "AGENT_MODE is not set to 'cloud' in .env — adding it now."
  echo "AGENT_MODE=cloud" >> "$REPO_DIR/.env"
fi

# Validate DRY_RUN=true for safety
if grep -q "^DRY_RUN=false" "$REPO_DIR/.env" 2>/dev/null; then
  warn "DRY_RUN=false is set! Cloud agent will perform real actions. Confirm this is intentional."
else
  info "DRY_RUN safety check: OK (true or not set)"
fi

# ── 9. Vault Git init (if VAULT_PATH set) ────────────────────────────────────

VAULT_PATH=$(grep "^VAULT_PATH=" "$REPO_DIR/.env" 2>/dev/null | cut -d= -f2 || true)
VAULT_GIT_REMOTE=$(grep "^VAULT_GIT_REMOTE=" "$REPO_DIR/.env" 2>/dev/null | cut -d= -f2 || true)

if [ -n "$VAULT_PATH" ] && [ -n "$VAULT_GIT_REMOTE" ]; then
  mkdir -p "$VAULT_PATH"
  if [ ! -d "$VAULT_PATH/.git" ]; then
    info "Initialising vault Git repo at $VAULT_PATH..."
    git -C "$VAULT_PATH" init
    git -C "$VAULT_PATH" remote add origin "$VAULT_GIT_REMOTE"
    git -C "$VAULT_PATH" pull origin main 2>/dev/null \
      || git -C "$VAULT_PATH" pull origin master 2>/dev/null \
      || warn "Could not pull from remote — push from Local first."
  else
    info "Vault Git repo already initialised."
  fi
else
  warn "VAULT_PATH or VAULT_GIT_REMOTE not set — skipping vault Git init."
fi

# ── 10. PM2 startup ───────────────────────────────────────────────────────────

info "Starting PM2 cloud processes..."
pm2 start "$REPO_DIR/pm2.cloud.config.js"
pm2 save

info "Configuring PM2 to start on reboot..."
pm2 startup systemd -u "$USER" --hp "$HOME" || warn "Run the pm2 startup command manually (shown above)."

info ""
info "=== Cloud Agent Setup Complete ==="
info "  Status:    pm2 status"
info "  Logs:      pm2 logs orchestrator"
info "  Stop all:  pm2 stop all"
info ""
info "Next: Push the vault from Local → Cloud to start syncing."
