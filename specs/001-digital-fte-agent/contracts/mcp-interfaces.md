# Contract: MCP Server Interfaces

**Branch**: `001-digital-fte-agent` | **Date**: 2026-02-22

All MCP servers use stdio transport. Claude Code invokes them via `mcp.json` configuration.
Each tool is listed with its name, input schema, output schema, and error behavior.
All MCP tools MUST respect `DRY_RUN` mode (log intent, return mock success, no real action).

---

## 1. email-mcp (Node.js)

**Transport**: stdio | **Config key**: `email`

### Tool: `email_send`

Sends an email via Gmail API.

**Input**:
```json
{
  "to": "string (required) — recipient email address",
  "subject": "string (required)",
  "body": "string (required) — plain text or HTML",
  "cc": "string (optional) — comma-separated CC addresses",
  "attachment_path": "string (optional) — absolute path to file"
}
```

**Output**:
```json
{
  "success": true,
  "message_id": "string — Gmail message ID",
  "timestamp": "ISO8601"
}
```

**Errors**:
- `AUTH_EXPIRED` — OAuth token invalid; watcher must alert human, halt email operations
- `QUOTA_EXCEEDED` — daily send quota hit; apply exponential backoff
- `INVALID_RECIPIENT` — bounce-back or invalid address; log, do not retry

**DRY_RUN behavior**: logs `[DRY RUN] Would send email to <to> subject: <subject>`, returns
`{"success": true, "message_id": "DRY_RUN_<timestamp>", "dry_run": true}`

---

### Tool: `email_draft`

Creates a Gmail draft without sending.

**Input**:
```json
{
  "to": "string (required)",
  "subject": "string (required)",
  "body": "string (required)",
  "attachment_path": "string (optional)"
}
```

**Output**:
```json
{
  "success": true,
  "draft_id": "string",
  "timestamp": "ISO8601"
}
```

**Notes**: Cloud agent ONLY uses `email_draft` — it MUST NOT call `email_send` (FR-024).

---

### Tool: `email_search`

Searches Gmail inbox.

**Input**:
```json
{
  "query": "string (required) — Gmail search query (e.g., 'is:unread is:important')",
  "max_results": "integer (optional, default 10)"
}
```

**Output**:
```json
{
  "messages": [
    {
      "id": "string",
      "from": "string",
      "subject": "string",
      "snippet": "string",
      "received": "ISO8601"
    }
  ],
  "count": "integer"
}
```

---

## 2. browser-mcp (Node.js + Playwright)

**Transport**: stdio | **Config key**: `browser`

### Tool: `browser_navigate`

Navigates to a URL and returns page content.

**Input**:
```json
{
  "url": "string (required)",
  "wait_for": "string (optional) — CSS selector to wait for before returning",
  "timeout_ms": "integer (optional, default 30000)"
}
```

**Output**:
```json
{
  "success": true,
  "url": "string — final URL after redirects",
  "title": "string",
  "text_content": "string — visible text content"
}
```

---

### Tool: `browser_click`

Clicks an element on the current page.

**Input**:
```json
{
  "selector": "string (required) — CSS selector or aria-label",
  "timeout_ms": "integer (optional, default 5000)"
}
```

**Output**:
```json
{
  "success": true,
  "element_text": "string — text of clicked element"
}
```

**DRY_RUN behavior**: logs action, returns `{"success": true, "dry_run": true}` without clicking.

---

### Tool: `browser_fill`

Fills a form field with text.

**Input**:
```json
{
  "selector": "string (required)",
  "value": "string (required)"
}
```

**Output**:
```json
{"success": true}
```

**DRY_RUN behavior**: logs `[DRY RUN] Would fill <selector> with <value>`.

---

## 3. calendar-mcp (Node.js)

**Transport**: stdio | **Config key**: `calendar`

### Tool: `calendar_create_event`

Creates a Google Calendar event.

**Input**:
```json
{
  "title": "string (required)",
  "start": "ISO8601 (required)",
  "end": "ISO8601 (required)",
  "description": "string (optional)",
  "attendees": "string[] (optional) — email addresses"
}
```

**Output**:
```json
{
  "success": true,
  "event_id": "string",
  "html_link": "string — calendar event URL"
}
```

---

### Tool: `calendar_list_events`

Lists upcoming events.

**Input**:
```json
{
  "max_results": "integer (optional, default 10)",
  "time_min": "ISO8601 (optional, default now)"
}
```

**Output**:
```json
{
  "events": [
    {
      "id": "string",
      "title": "string",
      "start": "ISO8601",
      "end": "ISO8601"
    }
  ]
}
```

---

## 4. odoo-mcp (Python MCP server)

**Transport**: stdio | **Config key**: `odoo`
**Auth**: `ODOO_URL`, `ODOO_DB`, `ODOO_API_KEY` env vars

### Tool: `odoo_search_read`

Reads records from any Odoo model (safe — no writes).

**Input**:
```json
{
  "model": "string (required) — e.g., 'account.move', 'res.partner'",
  "domain": "array (optional) — Odoo domain filter, e.g., [['state','=','draft']]",
  "fields": "string[] (optional) — fields to return",
  "limit": "integer (optional, default 20)"
}
```

**Output**:
```json
{
  "records": [{"id": 1, "name": "...", "...": "..."}],
  "count": "integer"
}
```

**Availability**: Cloud agent and Local agent (read is always safe).

---

### Tool: `odoo_create_draft`

Creates a draft record in Odoo (state=draft, not posted).

**Input**:
```json
{
  "model": "string (required) — e.g., 'account.move'",
  "values": "object (required) — field values for the new record",
  "approval_ref": "string (required) — /Pending_Approval/ filename requiring this"
}
```

**Output**:
```json
{
  "success": true,
  "record_id": "integer",
  "model": "string"
}
```

**Availability**: Cloud agent (draft only). Local agent calls after approval.

**DRY_RUN behavior**: logs intent, returns `{"success": true, "record_id": -1, "dry_run": true}`.

---

### Tool: `odoo_post_record`

Posts (confirms) a draft record in Odoo (irreversible — REQUIRES human approval).

**Input**:
```json
{
  "model": "string (required)",
  "record_id": "integer (required)",
  "approval_ref": "string (required) — /Approved/ filename authorizing this"
}
```

**Output**:
```json
{
  "success": true,
  "record_id": "integer",
  "new_state": "string"
}
```

**Availability**: Local agent ONLY. Cloud agent MUST NOT call this tool.

**Pre-condition**: `approval_ref` file must exist in `/Approved/` — server validates before executing.

---

## 5. Social MCP (via browser-mcp or dedicated social tool)

Social posting uses a combination of official API calls (via browser-mcp OAuth flows)
and structured `email_draft`-equivalent patterns.

For Gold+ tier, social posts are submitted via official platform APIs:
- LinkedIn: `POST /v2/ugcPosts` (LinkedIn API v2)
- Facebook/Instagram: `POST /{page-id}/feed` (Graph API v19+)
- Twitter/X: `POST /2/tweets` (Twitter API v2)

These calls are wrapped by the `browser-mcp` making authenticated HTTP requests.
All social posts MUST go through `/Pending_Approval/` first (FR-016).

---

## Claude Code MCP Configuration

```json
{
  "servers": {
    "email": {
      "command": "node",
      "args": ["src/mcp_servers/email_mcp/index.js"],
      "env": {
        "GMAIL_CREDENTIALS_PATH": "${GMAIL_CREDENTIALS_PATH}",
        "GMAIL_TOKEN_PATH": "${GMAIL_TOKEN_PATH}",
        "DRY_RUN": "${DRY_RUN}"
      }
    },
    "browser": {
      "command": "node",
      "args": ["src/mcp_servers/browser_mcp/index.js"],
      "env": {
        "HEADLESS": "true",
        "DRY_RUN": "${DRY_RUN}"
      }
    },
    "calendar": {
      "command": "node",
      "args": ["src/mcp_servers/calendar_mcp/index.js"],
      "env": {
        "GOOGLE_CREDENTIALS_PATH": "${GOOGLE_CREDENTIALS_PATH}",
        "DRY_RUN": "${DRY_RUN}"
      }
    },
    "odoo": {
      "command": "python",
      "args": ["src/mcp_servers/odoo_mcp/odoo_mcp.py"],
      "env": {
        "ODOO_URL": "${ODOO_URL}",
        "ODOO_DB": "${ODOO_DB}",
        "ODOO_API_KEY": "${ODOO_API_KEY}",
        "DRY_RUN": "${DRY_RUN}"
      }
    }
  }
}
```

---

## Error Taxonomy

| Error Code | Meaning | Recovery |
|-----------|---------|---------|
| `AUTH_EXPIRED` | OAuth token invalid | Halt ops + write ALERT + email human |
| `QUOTA_EXCEEDED` | API rate limit | Exponential backoff + local queue |
| `INVALID_INPUT` | Bad parameters | Log + skip (do not retry) |
| `NETWORK_TIMEOUT` | Transient network issue | Retry up to 3 times with backoff |
| `APPROVAL_MISSING` | No approval file found | Halt + error log |
| `DRY_RUN_ACTIVE` | DRY_RUN=true is set | Return mock success, log intent |
| `SERVER_ERROR` | Remote 5xx | Retry once; if persists, write ALERT |
