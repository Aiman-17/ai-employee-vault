/**
 * src/mcp_servers/calendar_mcp/index.js — Google Calendar MCP server (Silver tier).
 *
 * Exposes two tools to Claude Code:
 *   calendar_create_event — Create a calendar event (requires approval for external invites).
 *   calendar_list_events  — List upcoming events (read-only, always allowed).
 *
 * Authentication: shares the same OAuth2 token as email_mcp.
 *   GMAIL_TOKEN_PATH must point to a token with calendar scopes.
 *   Re-run scripts/setup_gmail_auth.py if calendar scope is missing.
 *
 * Start:  node src/mcp_servers/calendar_mcp/index.js
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
const TOKEN_PATH = process.env.GMAIL_TOKEN_PATH || path.resolve(__dirname, '../../../credentials/gmail_token.json');

// ── Calendar client (lazy-init) ───────────────────────────────────────────────

let calendarClient = null;

function getCalendarClient() {
  if (calendarClient) return calendarClient;

  if (!existsSync(TOKEN_PATH)) {
    throw new Error(
      `Token not found at ${TOKEN_PATH}. ` +
      `Run: python scripts/setup_gmail_auth.py (ensure calendar scope is included)`
    );
  }

  const token = JSON.parse(readFileSync(TOKEN_PATH, 'utf8'));
  const oauth2Client = new google.auth.OAuth2(
    token.client_id,
    token.client_secret,
    token.redirect_uri || 'urn:ietf:wg:oauth:2.0:oob',
  );
  oauth2Client.setCredentials(token);
  calendarClient = google.calendar({ version: 'v3', auth: oauth2Client });
  return calendarClient;
}

// ── Tool definitions ──────────────────────────────────────────────────────────

const TOOLS = [
  {
    name: 'calendar_create_event',
    description: [
      'Create a Google Calendar event.',
      'DRY_RUN=true (default) — logs intent without creating the event.',
      'External attendees always require human approval via Pending_Approval/.',
    ].join(' '),
    inputSchema: {
      type: 'object',
      properties: {
        title:       { type: 'string',  description: 'Event title / summary.' },
        start:       { type: 'string',  description: 'Start datetime in ISO 8601 (e.g. 2026-02-25T10:00:00).' },
        end:         { type: 'string',  description: 'End datetime in ISO 8601.' },
        description: { type: 'string',  description: 'Optional event description / agenda.' },
        location:    { type: 'string',  description: 'Optional event location.' },
        attendees:   {
          type: 'array',
          items: { type: 'string' },
          description: 'Optional list of attendee email addresses.',
        },
        calendar_id: { type: 'string',  description: 'Calendar ID (default: "primary").' },
      },
      required: ['title', 'start', 'end'],
    },
  },
  {
    name: 'calendar_list_events',
    description: 'List upcoming Google Calendar events. Read-only — always allowed.',
    inputSchema: {
      type: 'object',
      properties: {
        calendar_id:  { type: 'string', description: 'Calendar ID (default: "primary").' },
        max_results:  { type: 'number', description: 'Maximum events to return (default 10).', default: 10 },
        time_min:     { type: 'string', description: 'Start of time range in ISO 8601 (default: now).' },
        time_max:     { type: 'string', description: 'End of time range in ISO 8601 (default: 7 days from now).' },
        query:        { type: 'string', description: 'Optional free-text search query.' },
      },
    },
  },
];

// ── Tool handlers ─────────────────────────────────────────────────────────────

async function handleCreateEvent(params) {
  const {
    title,
    start,
    end,
    description = '',
    location = '',
    attendees = [],
    calendar_id = 'primary',
  } = params;

  if (DRY_RUN) {
    const msg = `[DRY RUN] Would create calendar event — Title: "${title}", Start: ${start}, Attendees: ${attendees.join(', ') || 'none'}`;
    console.error(msg);
    return { success: true, dry_run: true, message: msg };
  }

  try {
    const cal = getCalendarClient();
    const event = {
      summary: title,
      description,
      location,
      start: { dateTime: start, timeZone: 'UTC' },
      end:   { dateTime: end,   timeZone: 'UTC' },
    };

    if (attendees.length > 0) {
      event.attendees = attendees.map(email => ({ email }));
    }

    const result = await cal.events.insert({
      calendarId: calendar_id,
      requestBody: event,
      sendUpdates: attendees.length > 0 ? 'all' : 'none',
    });

    console.error(`Calendar event created — Event-ID: ${result.data.id}`);
    return {
      success: true,
      event_id: result.data.id,
      html_link: result.data.htmlLink,
      title,
      start,
      end,
    };
  } catch (err) {
    throw new Error(`calendar_create_event failed: ${err.message}`);
  }
}

async function handleListEvents(params) {
  const {
    calendar_id = 'primary',
    max_results = 10,
    time_min,
    time_max,
    query,
  } = params;

  try {
    const cal = getCalendarClient();
    const now = new Date().toISOString();
    const sevenDaysLater = new Date(Date.now() + 7 * 24 * 3600 * 1000).toISOString();

    const listParams = {
      calendarId: calendar_id,
      maxResults: Math.min(max_results, 50),
      timeMin: time_min || now,
      timeMax: time_max || sevenDaysLater,
      singleEvents: true,
      orderBy: 'startTime',
    };
    if (query) listParams.q = query;

    const result = await cal.events.list(listParams);
    const events = (result.data.items || []).map(ev => ({
      id: ev.id,
      title: ev.summary || '(No title)',
      start: ev.start?.dateTime || ev.start?.date || '',
      end:   ev.end?.dateTime   || ev.end?.date   || '',
      location: ev.location || '',
      description: ev.description || '',
      attendees: (ev.attendees || []).map(a => a.email),
      html_link: ev.htmlLink || '',
    }));

    return { events, total: events.length };
  } catch (err) {
    throw new Error(`calendar_list_events failed: ${err.message}`);
  }
}

// ── MCP server setup ──────────────────────────────────────────────────────────

const server = new Server(
  { name: 'digital-fte-calendar-mcp', version: '1.0.0' },
  { capabilities: { tools: {} } },
);

server.setRequestHandler(ListToolsRequestSchema, async () => ({ tools: TOOLS }));

server.setRequestHandler(CallToolRequestSchema, async (request) => {
  const { name, arguments: args } = request.params;

  try {
    let result;
    if (name === 'calendar_create_event') result = await handleCreateEvent(args);
    else if (name === 'calendar_list_events') result = await handleListEvents(args);
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
console.error(`Calendar MCP server running (DRY_RUN=${DRY_RUN})`);
