#!/usr/bin/env python3
"""List MCP tools from the deployed Genify profiler Databricks App.

Resolves the app URL via WorkspaceClient.apps.get (same pattern as Genify's MCP client),
then uses DatabricksMCPClient.list_tools().

Usage:
  python scripts/mcp_discover_profiler_tools.py

  python scripts/mcp_discover_profiler_tools.py --profile DEFAULT --app-name genify-mcp-profiler

  python scripts/mcp_discover_profiler_tools.py --server-url https://xxxx.cloud.databricks.com/.../mcp

Requires: pip install -r src/genify/requirements.txt (databricks-sdk, databricks-mcp)
"""
from __future__ import annotations

import argparse
import json
import sys


def main() -> int:
    parser = argparse.ArgumentParser(description="Discover MCP tools on the profiler app")
    parser.add_argument(
        "--profile",
        default="DEFAULT",
        help="Databricks CLI config profile (passed to WorkspaceClient)",
    )
    parser.add_argument(
        "--app-name",
        default="genify-mcp-profiler",
        help="Databricks Apps app name (must match app.yaml mcp_servers profiler app_name)",
    )
    parser.add_argument(
        "--server-url",
        default="",
        help="Skip apps lookup; use this MCP base URL (must include /mcp)",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Print one JSON array (name, description, inputSchema) to stdout",
    )
    args = parser.parse_args()

    try:
        from databricks.sdk import WorkspaceClient
        from databricks_mcp import DatabricksMCPClient
    except ImportError as e:
        print(
            "Missing dependency. Install Genify app requirements, e.g.:\n"
            "  pip install -r src/genify/requirements.txt\n"
            f"Import error: {e}",
            file=sys.stderr,
        )
        return 1

    ws = WorkspaceClient(profile=args.profile)

    if args.server_url.strip():
        server_url = args.server_url.strip().rstrip("/")
        if not server_url.endswith("/mcp"):
            server_url = f"{server_url}/mcp"
    else:
        try:
            app = ws.apps.get(args.app_name)
            server_url = f"{app.url.rstrip('/')}/mcp"
        except Exception as e:
            print(
                f"Failed to resolve app URL for {args.app_name!r} "
                f"(profile={args.profile!r}): {e}\n"
                "Use --server-url https://<your-app-host>/mcp if apps.get is unavailable.",
                file=sys.stderr,
            )
            return 1

    print(f"Profile: {args.profile}", file=sys.stderr)
    print(f"MCP URL: {server_url}", file=sys.stderr)

    client = DatabricksMCPClient(server_url=server_url, workspace_client=ws)
    tools = client.list_tools()

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
