#!/usr/bin/env bash
# =============================================================================
# scripts/setup_odoo_cloud.sh — Deploy Odoo Community on Cloud VM
#
# Requirements: Docker + Docker Compose installed on the VM
# Usage: bash scripts/setup_odoo_cloud.sh
#
# Deploys: Odoo 17 + PostgreSQL 15 + Nginx reverse proxy
# =============================================================================

set -euo pipefail

LOG_PREFIX="[setup_odoo_cloud]"
info()  { echo "$LOG_PREFIX INFO:  $*"; }
warn()  { echo "$LOG_PREFIX WARN:  $*" >&2; }
error() { echo "$LOG_PREFIX ERROR: $*" >&2; exit 1; }

REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
CONFIG_DIR="$REPO_DIR/config"
mkdir -p "$CONFIG_DIR/ssl"

# ── 1. Install Docker if not present ─────────────────────────────────────────

if ! command -v docker &>/dev/null; then
  info "Installing Docker..."
  curl -fsSL https://get.docker.com | sh
  sudo usermod -aG docker "$USER"
  warn "You may need to log out and back in for Docker group membership to take effect."
else
  info "Docker already installed: $(docker --version)"
fi

if ! command -v docker-compose &>/dev/null && ! docker compose version &>/dev/null 2>&1; then
  info "Installing Docker Compose plugin..."
  sudo apt-get install -y docker-compose-plugin
fi

# ── 2. Generate DB password if not in .env ───────────────────────────────────

ENV_FILE="$REPO_DIR/.env"
if ! grep -q "^ODOO_DB_PASSWORD=" "$ENV_FILE" 2>/dev/null; then
  GENERATED_PASS=$(python3 -c "import secrets; print(secrets.token_urlsafe(24))")
  echo "ODOO_DB_PASSWORD=$GENERATED_PASS" >> "$ENV_FILE"
  info "Generated ODOO_DB_PASSWORD and added to .env"
fi

# ── 3. Create Odoo config ─────────────────────────────────────────────────────

cat > "$CONFIG_DIR/odoo.conf" <<'EOF'
[options]
db_host = db
db_port = 5432
db_user = odoo
db_password = False
addons_path = /usr/lib/python3/dist-packages/odoo/addons
data_dir = /var/lib/odoo
logfile = /var/log/odoo/odoo.log
log_level = info
workers = 2
max_cron_threads = 1
limit_memory_hard = 2684354560
limit_memory_soft = 2147483648
limit_request = 8192
limit_time_cpu = 60
limit_time_real = 120
EOF
info "Created config/odoo.conf"

# ── 4. Create Nginx config ────────────────────────────────────────────────────

VM_IP=$(curl -s ifconfig.me 2>/dev/null || hostname -I | awk '{print $1}')

cat > "$CONFIG_DIR/nginx-odoo.conf" <<EOF
upstream odoo {
    server odoo:8069;
}

server {
    listen 80;
    server_name $VM_IP _;

    # Redirect to HTTPS when SSL cert is configured
    # Uncomment after adding SSL cert to config/ssl/
    # return 301 https://\$host\$request_uri;

    location / {
        proxy_pass http://odoo;
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto \$scheme;
        proxy_redirect off;
        client_max_body_size 200M;
        proxy_read_timeout 720s;
    }

    location /web/static/ {
        proxy_cache_valid 200 90d;
        proxy_buffering on;
        expires 864000;
        proxy_pass http://odoo;
    }
}

# HTTPS server (uncomment after adding certs to config/ssl/)
# server {
#     listen 443 ssl;
#     server_name yourdomain.com;
#     ssl_certificate     /etc/nginx/ssl/cert.crt;
#     ssl_certificate_key /etc/nginx/ssl/cert.key;
#     ssl_protocols TLSv1.2 TLSv1.3;
#     location / {
#         proxy_pass http://odoo;
#         ...
#     }
# }
EOF
info "Created config/nginx-odoo.conf (VM IP: $VM_IP)"

# ── 5. Start containers ───────────────────────────────────────────────────────

cd "$REPO_DIR"
info "Starting Odoo + PostgreSQL + Nginx..."
docker compose -f docker-compose.odoo.yml up -d

# Wait for Odoo to be healthy
info "Waiting for Odoo to be ready (up to 120s)..."
for i in $(seq 1 24); do
  if curl -sf "http://localhost:8069/web/health" >/dev/null 2>&1; then
    info "Odoo is up at http://$VM_IP:8069"
    break
  fi
  sleep 5
  echo -n "."
done

# ── 6. Setup backup cron ──────────────────────────────────────────────────────

BACKUP_SCRIPT="$REPO_DIR/scripts/backup_odoo.sh"
cat > "$BACKUP_SCRIPT" <<'BKEOF'
#!/usr/bin/env bash
# Daily Odoo database backup
BACKUP_DIR="${HOME}/odoo_backups"
mkdir -p "$BACKUP_DIR"
TIMESTAMP=$(date +%Y-%m-%d_%H-%M-%S)
docker exec odoo_db pg_dump -U odoo mycompany > "$BACKUP_DIR/mycompany_$TIMESTAMP.sql"
# Keep last 7 daily backups
ls -t "$BACKUP_DIR"/*.sql 2>/dev/null | tail -n +8 | xargs rm -f 2>/dev/null || true
echo "[backup_odoo] Backup complete: mycompany_$TIMESTAMP.sql"
BKEOF
chmod +x "$BACKUP_SCRIPT"

# Add to crontab if not already there
if ! crontab -l 2>/dev/null | grep -q "backup_odoo"; then
  (crontab -l 2>/dev/null; echo "0 2 * * * $BACKUP_SCRIPT >> $REPO_DIR/logs/backup_odoo.log 2>&1") | crontab -
  info "Daily backup cron scheduled at 02:00."
fi

info ""
info "=== Odoo Setup Complete ==="
info "  URL:          http://$VM_IP:8069"
info "  Admin login:  admin / (set on first run)"
info "  Logs:         docker compose -f docker-compose.odoo.yml logs -f odoo"
info "  Backup:       $BACKUP_SCRIPT"
info ""
info "Next steps:"
info "  1. Open http://$VM_IP:8069 and complete Odoo first-run setup"
info "  2. Update ODOO_URL in .env to http://$VM_IP:8069"
info "  3. Get API key: Odoo Settings -> Users -> your user -> API Keys"
info "  4. Set ODOO_API_KEY in .env"
