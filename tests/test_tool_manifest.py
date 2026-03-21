"""Unit tests for MCP tool manifest and planner tool block."""
from __future__ import annotations

import json
import logging
import sys
import unittest
from pathlib import Path

GENIFY_ROOT = Path(__file__).resolve().parents[1] / "src" / "genify"
if str(GENIFY_ROOT) not in sys.path:
    sys.path.insert(0, str(GENIFY_ROOT))

from backend.config import MCPToolOverridesConfig  # noqa: E402
from backend.mcp.tool_manifest import (  # noqa: E402
    build_tool_manifest,
    format_manifest_for_planner,
    normalize_input_schema,
    tools_for_auto_gather,
)
from backend.agent.planner import _tools_block_for_plan  # noqa: E402


def _discovered():
    return [
        {
            "name": "get_alpha",
            "description": "Alpha tool",
            "inputSchema": {"type": "object", "properties": {"table_fqn": {"type": "string"}}},
            "_server": "uc-functions",
        },
        {
            "name": "get_beta",
            "description": "Beta tool",
            "inputSchema": {},
            "_server": "profiler",
        },
    ]


class TestNormalizeInputSchema(unittest.TestCase):
    def test_none(self):
        self.assertEqual(normalize_input_schema(None), {})

    def test_dict(self):
        d = {"type": "object"}
        self.assertIs(normalize_input_schema(d), d)


class TestBuildToolManifest(unittest.TestCase):
    def test_hints_on_mcp_tool(self):
        ov = MCPToolOverridesConfig(
            tool_hints=(("get_alpha", "Use for section A"),),
            hidden_tools=frozenset(),
            extra_tools=(),
        )
        m = build_tool_manifest(_discovered(), ov)
        by_name = {r["name"]: r for r in m}
        self.assertEqual(by_name["get_alpha"]["hint"], "Use for section A")
        self.assertEqual(by_name["get_alpha"]["callable"], True)
        self.assertEqual(by_name["get_alpha"]["source"], "mcp")

    def test_hidden_excludes_from_manifest(self):
        ov = MCPToolOverridesConfig(
            tool_hints=(),
            hidden_tools=frozenset({"get_beta"}),
            extra_tools=(),
        )
        m = build_tool_manifest(_discovered(), ov)
        names = {r["name"] for r in m}
        self.assertIn("get_alpha", names)
        self.assertNotIn("get_beta", names)

    def test_extra_tools_planner_only(self):
        ov = MCPToolOverridesConfig(
            tool_hints=(),
            hidden_tools=frozenset(),
            extra_tools=(
                {
                    "name": "doc_only",
                    "description": "Documentation convention",
                    "inputSchema": {"type": "object", "properties": {}},
                },
            ),
        )
        m = build_tool_manifest(_discovered(), ov)
        row = next(r for r in m if r["name"] == "doc_only")
        self.assertEqual(row["source"], "config")
        self.assertFalse(row["callable"])

    def test_duplicate_extra_merges_description_as_hint(self):
        ov = MCPToolOverridesConfig(
            tool_hints=(),
            hidden_tools=frozenset(),
            extra_tools=(
                {"name": "get_alpha", "description": "Extra note from config"},
            ),
        )
        with self.assertLogs("backend.mcp.tool_manifest", level=logging.WARNING):
            m = build_tool_manifest(_discovered(), ov)
        row = next(r for r in m if r["name"] == "get_alpha")
        self.assertIn("Extra note from config", row.get("hint", ""))

    def test_json_serializable(self):
        ov = MCPToolOverridesConfig()
        m = build_tool_manifest(_discovered(), ov)
        json.dumps(m)


class TestToolsForAutoGather(unittest.TestCase):
    def test_hides_tools(self):
        ov = MCPToolOverridesConfig(hidden_tools=frozenset({"get_beta"}))
        g = tools_for_auto_gather(_discovered(), ov)
        self.assertEqual([t["name"] for t in g], ["get_alpha"])


class TestFormatManifestForPlanner(unittest.TestCase):
    def test_sorted_and_contains_schema(self):
        ov = MCPToolOverridesConfig()
        m = build_tool_manifest(_discovered(), ov)
        t1 = format_manifest_for_planner(m)
        t2 = format_manifest_for_planner(m)
        self.assertEqual(t1, t2)
        self.assertIn("### get_alpha", t1)
        self.assertIn("inputSchema", t1)
        self.assertIn("uc-functions", t1)

    def test_empty(self):
        self.assertIn("No MCP tools", format_manifest_for_planner([]))


class TestToolsBlockForPlan(unittest.TestCase):
    def test_manifest_preferred(self):
        ctx = {
            "_mcp_tool_manifest": [
                {"name": "z", "server": "s", "description": "d", "inputSchema": {}, "source": "mcp", "callable": True},
            ],
            "_tool_descriptions": "legacy should not win",
        }
        text = _tools_block_for_plan(ctx)
        self.assertIn("### z", text)
        self.assertNotIn("legacy", text)

    def test_legacy_fallback(self):
        ctx = {"_tool_descriptions": "- foo: bar"}
        text = _tools_block_for_plan(ctx)
        self.assertIn("Legacy", text)
        self.assertIn("foo", text)


if __name__ == "__main__":
    unittest.main()
