#!/usr/bin/env python3
"""List MCP tools from a Unity Catalog managed MCP endpoint.

Resolves the URL like Genify's MCPClient for type uc_managed:
  {workspace_host}/api/2.0/mcp/functions/{catalog}/{schema}

Defaults match src/genify/app.yaml (uc-functions server: agent_spark / custom_agent).

Usage:
  python scripts/mcp_discover_uc_tools.py

  python scripts/mcp_discover_uc_tools.py --profile fe-vm-v2 --catalog agent_spark --schema custom_agent

  python scripts/mcp_discover_uc_tools.py --server-url https://xxx.cloud.databricks.com/api/2.0/mcp/functions/cat/sch

Requires: pip install -r src/genify/requirements.txt
"""
from __future__ import annotations

import argparse
import json
import sys


def _tools_to_rows(tools) -> list[dict]:
    rows = []
    for t in tools:
        name = getattr(t, "name", str(t))
        desc = getattr(t, "description", "") or ""
        schema = getattr(t, "inputSchema", None)
        if schema is not None and hasattr(schema, "model_dump"):
            schema = schema.model_dump()
        elif schema is not None and not isinstance(schema, dict):
            schema = dict(schema) if hasattr(schema, "keys") else str(schema)
        rows.append({"name": name, "description": desc, "inputSchema": schema or {}})
    return rows


def main() -> int:
    parser = argparse.ArgumentParser(description="Discover MCP tools on UC managed functions endpoint")
    parser.add_argument(
        "--profile",
        default="fe-vm-v2",
        help="Databricks CLI config profile",
    )
    parser.add_argument(
        "--catalog",
        default="agent_spark",
        help="UC catalog (must match app.yaml uc-functions uc_catalog)",
    )
    parser.add_argument(
        "--schema",
        default="custom_agent",
        help="UC schema (must match app.yaml uc-functions uc_schema)",
    )
    parser.add_argument(
        "--server-url",
        default="",
        help="Full MCP functions URL; if set, catalog/schema are ignored",
    )
    parser.add_argument("--json", action="store_true", help="Print JSON array only")
    args = parser.parse_args()

    try:
        from databricks.sdk import WorkspaceClient
        from databricks_mcp import DatabricksMCPClient
    except ImportError as e:
        print(
            "pip install -r src/genify/requirements.txt\n"
            f"Import error: {e}",
            file=sys.stderr,
        )
        return 1

    ws = WorkspaceClient(profile=args.profile)

    if args.server_url.strip():
        server_url = args.server_url.strip().rstrip("/")
    else:
        host = ws.config.host.rstrip("/")
        if not host:
            print("WorkspaceClient has no host; check profile auth.", file=sys.stderr)
            return 1
        cat, sch = args.catalog.strip(), args.schema.strip()
        if not cat or not sch:
            print("--catalog and --schema are required unless --server-url is set.", file=sys.stderr)
            return 1
        server_url = f"{host}/api/2.0/mcp/functions/{cat}/{sch}"

    print(f"Profile: {args.profile}", file=sys.stderr)
    print(f"MCP URL: {server_url}", file=sys.stderr)

    client = DatabricksMCPClient(server_url=server_url, workspace_client=ws)
    tools = client.list_tools()
    rows = _tools_to_rows(tools)

    if args.json:
        print(json.dumps(rows, indent=2))
        return 0

    print(f"\n{len(rows)} tool(s):\n", file=sys.stderr)
    for r in rows:
        print(f"### {r['name']}")
        if r["description"]:
            print(r["description"].strip())
        print("inputSchema:")
        print(json.dumps(r["inputSchema"], indent=2))
        print()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
