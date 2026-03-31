/**
 * src/mcp_servers/email_mcp/index.js — Email MCP server (Silver tier).
 *
 * Exposes three tools to Claude Code:
 *   email_send    — Send an email via Gmail API (blocked in cloud mode).
 *   email_draft   — Create a Gmail draft (allowed in all modes).
 *   email_search  — Search Gmail inbox.
 *
 * Security rules (from the Digital FTE Constitution, Article IV):
 *   - DRY_RUN=true (default) → all send/draft actions are logged but not executed.
 *   - AGENT_MODE=cloud       → email_send is blocked; only email_draft is allowed.
 *   - Requires GMAIL_TOKEN_PATH pointing to a valid OAuth2 token.
 *
 * Start:  node src/mcp_servers/email_mcp/index.js
 * Via Claude Code: registered in .claude/settings.json
 */

import { Server } from '@modelcontextprotocol/sdk/server/index.js';
import { StdioServerTransport } from '@modelcontextprotocol/sdk/server/stdio.js';
import { CallToolRequestSchema, ListToolsRequestSchema } from '@modelcontextprotocol/sdk/types.js';
import { readFileSync, existsSync } from 'fs';
import { google } from 'googleapis';
import path from 'path';
import { fileURLToPath } from 'url';

const __dirname = path.dirname(fileURLToPath(import.meta.url));

// ── Environment ───────────────────────────────────────────────────────────────

const DRY_RUN = process.env.DRY_RUN !== 'false';  // true by default (safe)
const AGENT_MODE = process.env.AGENT_MODE || 'local';  // 'cloud' | 'local'
const TOKEN_PATH = process.env.GMAIL_TOKEN_PATH || path.resolve(__dirname, '../../../credentials/gmail_token.json');

// ── Gmail client (lazy-init) ──────────────────────────────────────────────────

let gmailClient = null;

function getGmailClient() {
  if (gmailClient) return gmailClient;

  if (!existsSync(TOKEN_PATH)) {
    throw new Error(
      `Gmail token not found at ${TOKEN_PATH}. ` +
      `Run: python scripts/setup_gmail_auth.py`
    );
  }

  const token = JSON.parse(readFileSync(TOKEN_PATH, 'utf8'));
  const oauth2Client = new google.auth.OAuth2(
    token.client_id,
    token.client_secret,
    token.redirect_uri || 'urn:ietf:wg:oauth:2.0:oob',
  );
  oauth2Client.setCredentials(token);
  gmailClient = google.gmail({ version: 'v1', auth: oauth2Client });
  return gmailClient;
}

// ── Tool definitions ──────────────────────────────────────────────────────────

const TOOLS = [
  {
    name: 'email_send',
    description: [
      'Send an email via Gmail.',
      'BLOCKED in cloud mode (AGENT_MODE=cloud) — creates a draft instead.',
      'BLOCKED when DRY_RUN=true (default) — logs intent without sending.',
      'Requires prior human approval via Pending_Approval/ workflow.',
    ].join(' '),
    inputSchema: {
      type: 'object',
      properties: {
        to:          { type: 'string', description: 'Recipient email address.' },
        subject:     { type: 'string', description: 'Email subject line.' },
        body:        { type: 'string', description: 'Plain-text or HTML email body.' },
        attachment:  { type: 'string', description: 'Optional: absolute path to attachment file.' },
        in_reply_to: { type: 'string', description: 'Optional: Gmail message ID to reply to.' },
      },
      required: ['to', 'subject', 'body'],
    },
  },
  {
    name: 'email_draft',
    description: [
      'Create a Gmail draft without sending.',
      'Allowed in all agent modes (local and cloud).',
    ].join(' '),
    inputSchema: {
      type: 'object',
      properties: {
        to:      { type: 'string', description: 'Recipient email address.' },
        subject: { type: 'string', description: 'Email subject line.' },
        body:    { type: 'string', description: 'Plain-text or HTML email body.' },
      },
      required: ['to', 'subject', 'body'],
    },
  },
  {
    name: 'email_search',
    description: 'Search Gmail messages using a Gmail query string (e.g. "from:boss@co.com is:unread").',
    inputSchema: {
      type: 'object',
      properties: {
        query:       { type: 'string', description: 'Gmail search query.' },
        max_results: { type: 'number', description: 'Maximum results to return (default 10).', default: 10 },
      },
      required: ['query'],
    },
  },
];

// ── Tool handlers ─────────────────────────────────────────────────────────────

async function handleEmailSend(params) {
  const { to, subject, body, attachment, in_reply_to } = params;

  // Security: cloud agents may not send directly
  if (AGENT_MODE === 'cloud') {
    const msg = `[CLOUD MODE] email_send blocked. Creating draft instead. To: ${to}, Subject: ${subject}`;
    console.error(msg);
    return handleEmailDraft({ to, subject, body });
  }

  if (DRY_RUN) {
    const msg = `[DRY RUN] Would send email — To: ${to}, Subject: ${subject}`;
    console.error(msg);
    return { success: true, dry_run: true, message: msg };
  }

  try {
    const gmail = getGmailClient();
    const raw = buildRawEmail({ to, subject, body, in_reply_to });
    const result = await gmail.users.messages.send({
      userId: 'me',
      requestBody: { raw },
    });
    console.error(`Email sent — Message-ID: ${result.data.id}`);
    return {
      success: true,
      message_id: result.data.id,
      to,
      subject,
    };
  } catch (err) {
    throw new Error(`email_send failed: ${err.message}`);
  }
}

async function handleEmailDraft(params) {
  const { to, subject, body } = params;

  if (DRY_RUN) {
    const msg = `[DRY RUN] Would create draft — To: ${to}, Subject: ${subject}`;
    console.error(msg);
    return { success: true, dry_run: true, message: msg };
  }

  try {
    const gmail = getGmailClient();
    const raw = buildRawEmail({ to, subject, body });
    const result = await gmail.users.drafts.create({
      userId: 'me',
      requestBody: { message: { raw } },
    });
    console.error(`Draft created — Draft-ID: ${result.data.id}`);
    return {
      success: true,
      draft_id: result.data.id,
      to,
      subject,
    };
  } catch (err) {
    throw new Error(`email_draft failed: ${err.message}`);
  }
}

async function handleEmailSearch(params) {
  const { query, max_results = 10 } = params;

  try {
    const gmail = getGmailClient();
    const listResult = await gmail.users.messages.list({
      userId: 'me',
      q: query,
      maxResults: Math.min(max_results, 50),
    });

    const messages = listResult.data.messages || [];
    const results = await Promise.all(
      messages.slice(0, max_results).map(async (m) => {
        const detail = await gmail.users.messages.get({
          userId: 'me',
          id: m.id,
          format: 'metadata',
          metadataHeaders: ['From', 'Subject', 'Date'],
        });
        const headers = Object.fromEntries(
          (detail.data.payload?.headers || []).map(h => [h.name, h.value])
        );
        return {
          id: m.id,
          from: headers['From'] || '',
          subject: headers['Subject'] || '',
          date: headers['Date'] || '',
          snippet: detail.data.snippet || '',
        };
      })
    );

    return { results, total_found: listResult.data.resultSizeEstimate || results.length };
  } catch (err) {
    throw new Error(`email_search failed: ${err.message}`);
  }
}

// ── RFC 2822 email builder ────────────────────────────────────────────────────

function buildRawEmail({ to, subject, body, in_reply_to }) {
  const lines = [
    `To: ${to}`,
    `Subject: ${subject}`,
    'MIME-Version: 1.0',
    'Content-Type: text/plain; charset=utf-8',
  ];
  if (in_reply_to) lines.push(`In-Reply-To: ${in_reply_to}`);
  lines.push('', body);
  const raw = lines.join('\r\n');
  return Buffer.from(raw).toString('base64url');
}

// ── MCP server setup ──────────────────────────────────────────────────────────

const server = new Server(
  { name: 'digital-fte-email-mcp', version: '1.0.0' },
  { capabilities: { tools: {} } },
);

server.setRequestHandler(ListToolsRequestSchema, async () => ({ tools: TOOLS }));

server.setRequestHandler(CallToolRequestSchema, async (request) => {
  const { name, arguments: args } = request.params;

  try {
    let result;
    if (name === 'email_send')   result = await handleEmailSend(args);
    else if (name === 'email_draft')  result = await handleEmailDraft(args);
    else if (name === 'email_search') result = await handleEmailSearch(args);
    else throw new Error(`Unknown tool: ${name}`);

    return {
      content: [{ type: 'text', text: JSON.stringify(result, null, 2) }],
    };
  } catch (err) {
    return {
      content: [{ type: 'text', text: `Error: ${err.message}` }],
      isError: true,
    };
  }
});

// ── Start ─────────────────────────────────────────────────────────────────────

const transport = new StdioServerTransport();
await server.connect(transport);
console.error(`Email MCP server running (DRY_RUN=${DRY_RUN}, AGENT_MODE=${AGENT_MODE})`);
