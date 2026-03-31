"""
src/mcp_servers/odoo_mcp/__init__.py — Odoo MCP Server package.

Exposes three MCP tools for interacting with an Odoo Community instance
via XML-RPC (compatible with Odoo 16, 17, 18, 19+):

  - odoo_search_read : Query records from any Odoo model
  - odoo_create_draft: Create a draft record (DRY_RUN guarded)
  - odoo_post_record : Post/validate a draft record (HITL approval gate)

Run standalone:
    uv run python -m src.mcp_servers.odoo_mcp.server

Via Claude Code:
    Registered in .claude/settings.json as the "odoo" MCP server.
"""
