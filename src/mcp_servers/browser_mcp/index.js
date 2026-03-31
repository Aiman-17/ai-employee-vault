/**
 * src/mcp_servers/browser_mcp/index.js — Browser MCP Server for Digital FTE Agent.
 *
 * Exposes four Playwright-powered browser tools via MCP (stdio transport):
 *   - browser_navigate   : Navigate to a URL (payment domains require approval)
 *   - browser_click      : Click an element by CSS / Playwright selector
 *   - browser_fill       : Fill a form field value
 *   - browser_screenshot : Take a screenshot, saved to VAULT_PATH/Screenshots/
 *
 * Security:
 *   - AGENT_MODE=cloud → payment/banking domain navigation is blocked
 *   - Payment domains without a valid approval_token → write Pending_Approval card
 *   - DRY_RUN=true     → log intent only, skip actual browser actions
 *
 * Usage (standalone):
 *   node src/mcp_servers/browser_mcp/index.js
 *
 * Usage (via Claude Code):
 *   Registered automatically via .claude/settings.json "browser" MCP entry.
 */

import { chromium } from 'playwright';
import { McpServer } from '@modelcontextprotocol/sdk/server/mcp.js';
import { StdioServerTransport } from '@modelcontextprotocol/sdk/server/stdio.js';
import { z } from 'zod';
import fs from 'fs';
import path from 'path';

// ── Configuration ─────────────────────────────────────────────────────────────

const VAULT_PATH = process.env.VAULT_PATH || '.';
const AGENT_MODE = (process.env.AGENT_MODE || 'local').toLowerCase();
const DRY_RUN = (process.env.DRY_RUN || 'true').toLowerCase() === 'true';

/** Domains that require HITL approval before navigation */
const PAYMENT_DOMAINS = [
  'paypal.com',
  'stripe.com',
  'wise.com',
  'payoneer.com',
  'revolut.com',
  'transferwise.com',
  '/bank.',
  '/banking.',
  '/payments.',
  '/checkout.',
  'americanexpress.com',
  'wellsfargo.com',
  'chase.com',
  'hsbc.com',
  'barclays.co.uk',
];

// ── Browser lifecycle ─────────────────────────────────────────────────────────

let browser = null;
let page = null;

async function getBrowser() {
  if (!browser || !browser.isConnected()) {
    browser = await chromium.launch({ headless: true });
  }
  return browser;
}

async function getPage() {
  const b = await getBrowser();
  if (!page || page.isClosed()) {
    const ctx = await b.newContext();
    page = await ctx.newPage();
  }
  return page;
}

// ── Helpers ───────────────────────────────────────────────────────────────────

function isPaymentDomain(url) {
  const lower = url.toLowerCase();
  return PAYMENT_DOMAINS.some(d => lower.includes(d));
}

function approvalExists(token) {
  const f = path.join(VAULT_PATH, 'Approved', `${token}.md`);
  return fs.existsSync(f);
}

function ensurePendingApprovalCard(token, url) {
  const dir = path.join(VAULT_PATH, 'Pending_Approval');
  fs.mkdirSync(dir, { recursive: true });
  const pending = path.join(dir, `${token}.md`);
  if (!fs.existsSync(pending)) {
    const today = new Date().toISOString().split('T')[0];
    fs.writeFileSync(
      pending,
      `---\ntype: browser_navigation_approval\nurl: ${url}\ntoken: ${token}\n` +
      `status: pending\ncreated: ${today}\n---\n\n` +
      `## Browser Navigation Approval\n\n` +
      `Your Digital FTE wants to navigate to a payment/banking URL:\n\n` +
      `> \`${url}\`\n\n` +
      `## To Approve\n` +
      `Move this file to \`/Approved\` to allow navigation.\n\n` +
      `## To Reject\n` +
      `Move this file to \`/Rejected\` to cancel.\n`,
      'utf8'
    );
  }
  return pending;
}

// ── MCP Server ────────────────────────────────────────────────────────────────

const server = new McpServer({
  name: 'browser',
  version: '1.0.0',
});

// ── browser_navigate ──────────────────────────────────────────────────────────

server.tool(
  'browser_navigate',
  {
    url: z.string().describe('Fully-qualified URL to navigate to'),
    approval_token: z.string().optional().describe(
      'Required for payment/banking domains — stem of an approval file in Approved/'
    ),
  },
  async ({ url, approval_token }) => {
    // Block payment domains in cloud mode
    if (AGENT_MODE === 'cloud' && isPaymentDomain(url)) {
      return {
        content: [{
          type: 'text',
          text: `[BLOCKED] Cloud agent is not permitted to navigate to payment domain: ${url}`,
        }],
      };
    }

    // Require HITL approval for payment domains
    if (isPaymentDomain(url)) {
      const token = approval_token || `BROWSER_${Date.now()}`;
      if (!approvalExists(token)) {
        const pending = ensurePendingApprovalCard(token, url);
        return {
          content: [{
            type: 'text',
            text:
              `[APPROVAL REQUIRED] Payment domain detected.\n` +
              `Approval card: ${pending}\n` +
              `Move it to /Approved, then retry with approval_token="${token}".`,
          }],
        };
      }
    }

    if (DRY_RUN) {
      return { content: [{ type: 'text', text: `[DRY RUN] Would navigate to: ${url}` }] };
    }

    const p = await getPage();
    await p.goto(url, { waitUntil: 'domcontentloaded', timeout: 30000 });
    const title = await p.title();
    return {
      content: [{ type: 'text', text: `Navigated to: ${p.url()} — Title: "${title}"` }],
    };
  }
);

// ── browser_click ─────────────────────────────────────────────────────────────

server.tool(
  'browser_click',
  {
    selector: z.string().describe('CSS selector or Playwright locator string to click'),
  },
  async ({ selector }) => {
    if (DRY_RUN) {
      return { content: [{ type: 'text', text: `[DRY RUN] Would click: ${selector}` }] };
    }
    const p = await getPage();
    await p.click(selector, { timeout: 10000 });
    return { content: [{ type: 'text', text: `Clicked: ${selector}` }] };
  }
);

// ── browser_fill ──────────────────────────────────────────────────────────────

server.tool(
  'browser_fill',
  {
    selector: z.string().describe('CSS selector or Playwright locator for the input field'),
    text: z.string().describe('Value to fill into the field'),
  },
  async ({ selector, text }) => {
    if (DRY_RUN) {
      return {
        content: [{ type: 'text', text: `[DRY RUN] Would fill "${selector}" (${text.length} chars)` }],
      };
    }
    const p = await getPage();
    await p.fill(selector, text, { timeout: 10000 });
    return { content: [{ type: 'text', text: `Filled: ${selector}` }] };
  }
);

// ── browser_screenshot ────────────────────────────────────────────────────────

server.tool(
  'browser_screenshot',
  {
    filename: z.string().optional().describe(
      'Filename for the screenshot (saved in VAULT_PATH/Screenshots/). ' +
      'Defaults to screenshot_<timestamp>.png'
    ),
  },
  async ({ filename }) => {
    const screenshotsDir = path.join(VAULT_PATH, 'Screenshots');
    fs.mkdirSync(screenshotsDir, { recursive: true });
    const fname = filename || `screenshot_${Date.now()}.png`;
    const filepath = path.join(screenshotsDir, fname);

    if (DRY_RUN) {
      return {
        content: [{ type: 'text', text: `[DRY RUN] Would save screenshot to: ${filepath}` }],
      };
    }

    const p = await getPage();
    await p.screenshot({ path: filepath, fullPage: false });
    return { content: [{ type: 'text', text: `Screenshot saved: ${filepath}` }] };
  }
);

// ── Clean up browser on exit ──────────────────────────────────────────────────

process.on('exit', async () => {
  if (browser) {
    await browser.close().catch(() => {});
  }
});

process.on('SIGINT', () => process.exit(0));
process.on('SIGTERM', () => process.exit(0));

// ── Start server ──────────────────────────────────────────────────────────────

const transport = new StdioServerTransport();
await server.connect(transport);
