// =============================================================================
// Digital FTE Agent — PM2 Local Process Manager Configuration
// Run: pm2 start pm2.config.js
// Status: pm2 status | Stop: pm2 stop all | Logs: pm2 logs orchestrator
// Tip: pm2 save && pm2 startup  →  persist across reboots
// =============================================================================

module.exports = {
  apps: [
    {
      // Master orchestrator — dispatches tasks from Needs_Action/
      name: 'orchestrator',
      script: 'src/orchestrator/main.py',        // entry point wires up all components
      interpreter: 'python3',
      cwd: __dirname,
      restart_delay: 3000,
      max_restarts: 5,
      min_uptime: '10s',
      watch: false,
      out_file: 'logs/orchestrator.log',
      error_file: 'logs/orchestrator-error.log',
      env: {
        PYTHONPATH: __dirname,
      },
    },
    {
      // Bronze tier: monitors FILE_DROP_PATH for new files
      name: 'filesystem_watcher',
      script: 'src/watchers/filesystem_watcher.py',
      interpreter: 'python3',
      cwd: __dirname,
      restart_delay: 3000,
      max_restarts: 20,
      watch: false,
      out_file: 'logs/filesystem_watcher.log',
      error_file: 'logs/filesystem_watcher-error.log',
      env: {
        PYTHONPATH: __dirname,
      },
    },
    {
      name: 'gmail_watcher',
      script: 'src/watchers/gmail_watcher.py',
      interpreter: 'python3',
      cwd: __dirname,
      restart_delay: 5000,
      max_restarts: 10,
      watch: false,
      log_file: 'logs/gmail_watcher.log',
      error_file: 'logs/gmail_watcher-error.log',
      env: {
        PYTHONPATH: __dirname,
      },
    },
    {
      name: 'whatsapp_watcher',
      script: 'src/watchers/whatsapp_watcher.py',
      interpreter: 'python3',
      cwd: __dirname,
      restart_delay: 5000,
      max_restarts: 10,
      watch: false,
      log_file: 'logs/whatsapp_watcher.log',
      error_file: 'logs/whatsapp_watcher-error.log',
      env: {
        PYTHONPATH: __dirname,
      },
    },
    {
      name: 'facebook_watcher',
      script: 'src/watchers/facebook_watcher.py',
      interpreter: 'python3',
      cwd: __dirname,
      restart_delay: 5000,
      max_restarts: 10,
      watch: false,
      log_file: 'logs/facebook_watcher.log',
      error_file: 'logs/facebook_watcher-error.log',
      env: {
        PYTHONPATH: __dirname,
      },
    },
    {
      name: 'instagram_watcher',
      script: 'src/watchers/instagram_watcher.py',
      interpreter: 'python3',
      cwd: __dirname,
      restart_delay: 5000,
      max_restarts: 10,
      watch: false,
      log_file: 'logs/instagram_watcher.log',
      error_file: 'logs/instagram_watcher-error.log',
      env: {
        PYTHONPATH: __dirname,
      },
    },
    {
      name: 'finance_watcher',
      script: 'src/watchers/finance_watcher.py',
      interpreter: 'python3',
      cwd: __dirname,
      restart_delay: 3000,
      max_restarts: 20,
      watch: false,
      log_file: 'logs/finance_watcher.log',
      error_file: 'logs/finance_watcher-error.log',
      env: {
        PYTHONPATH: __dirname,
      },
    },
    {
      name: 'watchdog',
      script: 'src/orchestrator/watchdog.py',
      interpreter: 'python3',
      cwd: __dirname,
      restart_delay: 10000,
      max_restarts: 5,
      watch: false,
      log_file: 'logs/watchdog.log',
      error_file: 'logs/watchdog-error.log',
      env: {
        PYTHONPATH: __dirname,
      },
    },
    // ── Gold: Odoo MCP server (standalone mode, also registered in .claude/settings.json)
    // Runs as a persistent stdio process for direct integration testing.
    // In normal Claude Code operation this is launched on-demand via .claude/settings.json.
    {
      name: 'odoo_mcp',
      script: 'src/mcp_servers/odoo_mcp/server.py',
      interpreter: 'python3',
      cwd: __dirname,
      restart_delay: 5000,
      max_restarts: 10,
      watch: false,
      out_file: 'logs/odoo_mcp.log',
      error_file: 'logs/odoo_mcp-error.log',
      env: {
        PYTHONPATH: __dirname,
        // ODOO_URL, ODOO_DB, ODOO_USERNAME, ODOO_PASSWORD loaded from .env
      },
    },
  ],
};
