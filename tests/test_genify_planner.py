"""Unit tests for Genify planner helpers (parse, tools block, fallback)."""
from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path

GENIFY_ROOT = Path(__file__).resolve().parents[1] / "src" / "genify"
if str(GENIFY_ROOT) not in sys.path:
    sys.path.insert(0, str(GENIFY_ROOT))

from backend.agent.planner import (  # noqa: E402
    _fallback_plan,
    _parse_plan_json,
    _tools_block_for_plan,
)


class TestParsePlanJson(unittest.TestCase):
    def test_plain_json(self):
        raw = '{"plan": [{"step": 1, "section_key": "a", "strategy": "skip"}]}'
        out = _parse_plan_json(raw)
        self.assertEqual(len(out["plan"]), 1)
        self.assertEqual(out["plan"][0]["section_key"], "a")

    def test_fenced_json(self):
        raw = """```json
{"plan": [], "total_auto_fill": 0, "total_ask": 0}
```"""
        out = _parse_plan_json(raw)
        self.assertEqual(out["plan"], [])


class TestToolsBlockForPlan(unittest.TestCase):
    def test_prefers_manifest(self):
        ctx = {
            "_mcp_tool_manifest": [
                {
                    "name": "get_table_profile",
                    "server": "s1",
                    "description": "profile",
                    "inputSchema": {"type": "object"},
                    "callable": True,
                    "source": "mcp",
                }
            ],
        }
        text = _tools_block_for_plan(ctx)
        self.assertIn("get_table_profile", text)
        self.assertIn("callable: True", text)

    def test_legacy_tool_descriptions(self):
        ctx = {"_tool_descriptions": "  tool a\n  tool b  "}
        text = _tools_block_for_plan(ctx)
        self.assertIn("Legacy cached tool list", text)
        self.assertIn("tool a", text)

    def test_empty_manifest(self):
        text = _tools_block_for_plan({"_mcp_tool_manifest": []})
        self.assertIn("No MCP tools discovered", text)


class TestFallbackPlan(unittest.TestCase):
    def test_keys_and_hands_off(self):
        sections = [{"key": "core"}, {"key": "extra"}]
        steps = _fallback_plan(sections, "hands_off")
        self.assertEqual(len(steps), 2)
        self.assertEqual(steps[0]["section_key"], "core")
        self.assertEqual(steps[0]["strategy"], "auto_fill")
        self.assertEqual(steps[1]["strategy"], "auto_fill")

    def test_interactive_mode_strategy(self):
        sections = [{"key": "only"}]
        steps = _fallback_plan(sections, "interactive")
        self.assertEqual(steps[0]["strategy"], "partial_fill_then_ask")


if __name__ == "__main__":
    unittest.main()
