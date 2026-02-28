// =============================================================================
// Digital FTE Agent — PM2 Cloud VM Process Manager Configuration
// Run: pm2 start pm2.cloud.config.js
//
// Cloud security rules (Constitution Article IX):
//   - NO whatsapp_watcher (session must stay on Local machine)
//   - ALL processes run with AGENT_MODE=cloud
//   - Cloud agent has draft-only authority; no payment credentials
// =============================================================================

module.exports = {
  apps: [
    {
      // Cloud orchestrator — draft-only mode, processes Needs_Action and Pending_Approval
      name: 'orchestrator',
      script: 'src/orchestrator/main.py',
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
        AGENT_MODE: 'cloud',
      },
    },
    {
      // Email triage + draft replies (cloud-mode: send blocked, draft only)
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
        AGENT_MODE: 'cloud',
      },
    },
    {
      // Finance monitoring — read-only, writing to Accounting/ only
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
        AGENT_MODE: 'cloud',
      },
    },
    {
      // Health monitor — restarts crashed cloud processes
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
        AGENT_MODE: 'cloud',
      },
    },
    // Note: whatsapp_watcher intentionally EXCLUDED from cloud config.
    // Constitution Article IX: WhatsApp session must stay on Local machine only.
    // Note: odoo_mcp included here for draft accounting actions only.
    //       Final posting (invoices, payments) requires Local approval.
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
        AGENT_MODE: 'cloud',
      },
    },
  ],
};
