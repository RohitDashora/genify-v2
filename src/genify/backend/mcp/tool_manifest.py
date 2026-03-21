"""Build MCP tool manifest for planning + persistence; optional app.yaml overrides."""
from __future__ import annotations

import json
import logging
from typing import Any

from backend.config import MCPToolOverridesConfig

logger = logging.getLogger(__name__)


def normalize_input_schema(schema: Any) -> dict[str, Any]:
    """Return a JSON-serializable dict for tool inputSchema."""
    if schema is None:
        return {}
    if isinstance(schema, dict):
        return schema
    if hasattr(schema, "model_dump"):
        try:
            return schema.model_dump()
        except Exception:
            pass
    if hasattr(schema, "__dict__"):
        try:
            return {k: v for k, v in vars(schema).items() if not k.startswith("_")}
        except Exception:
            pass
    try:
        return json.loads(json.dumps(schema, default=str))
    except (TypeError, ValueError):
        return {}


def _hints_map(overrides: MCPToolOverridesConfig) -> dict[str, str]:
    return dict(overrides.tool_hints)


def build_tool_manifest(
    discovered: list[dict],
    overrides: MCPToolOverridesConfig,
) -> list[dict[str, Any]]:
    """Merge MCP discovery with overrides into a stable manifest for planner + DB."""
    hidden = overrides.hidden_tools
    hints = _hints_map(overrides)
    manifest: list[dict[str, Any]] = []
    seen_names: set[str] = set()

    extra_by_name: dict[str, dict[str, Any]] = {}
    for raw in overrides.extra_tools:
        name = str(raw.get("name", "")).strip()
        if not name:
            continue
        if name in hidden:
            continue
        extra_by_name[name] = raw

    for tool in discovered:
        name = tool.get("name", "")
        if not name or name in hidden:
            continue
        server = tool.get("_server", "")
        desc = tool.get("description") or ""
        schema = normalize_input_schema(tool.get("inputSchema"))
        row: dict[str, Any] = {
            "name": name,
            "server": server,
            "description": desc,
            "inputSchema": schema,
            "source": "mcp",
            "callable": True,
        }
        if name in hints:
            row["hint"] = hints[name]
        if name in extra_by_name:
            extra = extra_by_name[name]
            extra_desc = str(extra.get("description", "")).strip()
            if extra_desc:
                logger.warning(
                    "mcp_tool_overrides: extra_tools duplicates discovered tool %r; "
                    "using discovered callable row; appending config description as hint",
                    name,
                )
                note = extra_desc
                if "hint" in row:
                    row["hint"] = f"{row['hint']}\n{note}"
                else:
                    row["hint"] = note
            ex_schema = extra.get("inputSchema")
            if ex_schema is not None and normalize_input_schema(ex_schema) != schema:
                logger.warning(
                    "mcp_tool_overrides: extra_tools inputSchema for %r ignored (discovered wins)",
                    name,
                )
        manifest.append(row)
        seen_names.add(name)

    for name, raw in sorted(extra_by_name.items(), key=lambda x: x[0]):
        if name in seen_names:
            continue
        desc = str(raw.get("description", "")).strip()
        if not desc:
            logger.warning("mcp_tool_overrides: extra_tools %r missing description, skipped", name)
            continue
        manifest.append({
            "name": name,
            "server": "",
            "description": desc,
            "inputSchema": normalize_input_schema(raw.get("inputSchema")),
            "source": "config",
            "callable": False,
        })
        if name in hints:
            manifest[-1]["hint"] = hints[name]

    return manifest


def tools_for_auto_gather(discovered: list[dict], overrides: MCPToolOverridesConfig) -> list[dict]:
    """Discovered registry tools minus hidden_tools (still uses name, inputSchema, _server)."""
    hidden = overrides.hidden_tools
    return [t for t in discovered if t.get("name") and t["name"] not in hidden]


def format_manifest_for_planner(manifest: list[dict[str, Any]]) -> str:
    """Stable, readable text for PLANNING_PROMPT (names, server, schema, callable flag)."""
    if not manifest:
        return "No MCP tools discovered."
    lines: list[str] = []
    for row in sorted(manifest, key=lambda r: r.get("name", "")):
        name = row.get("name", "")
        server = row.get("server", "")
        desc = (row.get("description") or "").strip()
        hint = (row.get("hint") or "").strip()
        source = row.get("source", "mcp")
        callable_ = row.get("callable", True)
        schema = row.get("inputSchema") or {}
        try:
            schema_text = json.dumps(schema, sort_keys=True, indent=2)
        except (TypeError, ValueError):
            schema_text = str(schema)
        lines.append(f"### {name}")
        lines.append(f"- server: {server or '(n/a)'}")
        lines.append(f"- source: {source}")
        lines.append(f"- callable: {callable_}")
        if desc:
            lines.append(f"- description: {desc}")
        if hint:
            lines.append(f"- planner_hint: {hint}")
        lines.append("- inputSchema:")
        for sl in schema_text.split("\n"):
            lines.append(f"  {sl}")
        lines.append("")
    return "\n".join(lines).strip()
