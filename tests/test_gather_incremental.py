"""Incremental MCP gather: _mcp_needs_gather, seed merge, gather iterator behavior."""
from __future__ import annotations

import asyncio
import sys
import unittest
import uuid
from pathlib import Path
from unittest.mock import MagicMock, patch

GENIFY_ROOT = Path(__file__).resolve().parents[1] / "src" / "genify"
if str(GENIFY_ROOT) not in sys.path:
    sys.path.insert(0, str(GENIFY_ROOT))

from backend.agent.core import (  # noqa: E402
    _MCP_GATHER_COMPLETE_KEY,
    _iter_gather_context_events,
    _mcp_needs_gather,
    _seed_merged_table_context,
)


class TestMcpNeedsGather(unittest.TestCase):
    def test_empty_needs_gather(self):
        self.assertTrue(_mcp_needs_gather({}))

    def test_missing_flag_needs_gather(self):
        self.assertTrue(_mcp_needs_gather({"a.b.c": {"t": 1}}))

    def test_false_flag_needs_gather(self):
        self.assertTrue(
            _mcp_needs_gather(
                {"a.b.c": {"t": 1}, _MCP_GATHER_COMPLETE_KEY: False}
            )
        )

    def test_complete_skips_gather(self):
        self.assertFalse(
            _mcp_needs_gather(
                {
                    "a.b.c": {"t": 1},
                    _MCP_GATHER_COMPLETE_KEY: True,
                }
            )
        )


class TestSeedMergedTableContext(unittest.TestCase):
    def test_strips_metadata_keys(self):
        raw = {
            "_mcp_tool_manifest": [{"name": "x"}],
            "_mcp_gather_complete": True,
            "cat.sch.t": {"p": 1},
        }
        out = _seed_merged_table_context(raw)
        self.assertEqual(out, {"cat.sch.t": {"p": 1}})

    def test_deep_copies_nested(self):
        raw = {"a.b.c": {"tool": {"nested": 1}}}
        out = _seed_merged_table_context(raw)
        out["a.b.c"]["tool"]["nested"] = 2
        self.assertEqual(raw["a.b.c"]["tool"]["nested"], 1)


class TestIterGatherIncremental(unittest.TestCase):
    def test_skips_cached_cell_no_call_tool(self):
        streamer = MagicMock()

        def trace(kind, msg, **kwargs):
            ev = {"kind": kind, "msg": msg, **kwargs}
            return ev

        streamer.trace.side_effect = trace

        session = {
            "table_ref": {
                "catalog": "c",
                "schema": "s",
                "table": "t",
            },
            "context_cache": {
                "c.s.t": {"existing_tool": {"ok": True}},
            },
        }
        out: dict = {}
        pool = MagicMock()
        sid = str(uuid.uuid4())

        registry = MagicMock()
        registry.connect_all = MagicMock()
        registry.get_available_tools.return_value = [
            {
                "name": "existing_tool",
                "inputSchema": {"properties": {"table_fqn": {}}},
            },
        ]

        async def run():
            with patch(
                "backend.agent.core.MCPRegistry",
                return_value=registry,
            ), patch(
                "backend.agent.core.tools_for_auto_gather",
                return_value=registry.get_available_tools.return_value,
            ), patch(
                "backend.agent.core.build_tool_manifest",
                return_value=[{"name": "existing_tool", "server": "s"}],
            ), patch(
                "backend.agent.core._save_context_cache",
            ) as save_mock:
                agen = _iter_gather_context_events(
                    session, streamer, out, pool, sid
                )
                async for _ in agen:
                    pass
            return save_mock

        save_mock = asyncio.run(run())
        registry.call_tool.assert_not_called()
        self.assertTrue(out["context"].get(_MCP_GATHER_COMPLETE_KEY))
        # Final save + possible partial saves (none if all skipped)
        self.assertGreaterEqual(save_mock.call_count, 1)
        self.assertEqual(
            out["context"]["c.s.t"]["existing_tool"],
            {"ok": True},
        )

    def test_calls_missing_tool_only(self):
        streamer = MagicMock()
        streamer.trace.side_effect = lambda *a, **k: {}

        session = {
            "table_ref": {
                "catalog": "c",
                "schema": "s",
                "table": "t",
            },
            "context_cache": {
                "c.s.t": {"warm": {"v": 1}},
            },
        }
        out: dict = {}
        pool = MagicMock()
        sid = str(uuid.uuid4())

        tools = [
            {
                "name": "warm",
                "inputSchema": {"properties": {"table_fqn": {}}},
            },
            {
                "name": "cold",
                "inputSchema": {"properties": {"table_fqn": {}}},
            },
        ]
        registry = MagicMock()
        registry.connect_all = MagicMock()
        registry.get_available_tools.return_value = tools

        def call_tool(name, args):
            if name == "cold":
                return {"fresh": True}
            raise AssertionError(f"unexpected tool {name}")

        registry.call_tool.side_effect = call_tool

        async def run():
            with patch(
                "backend.agent.core.MCPRegistry",
                return_value=registry,
            ), patch(
                "backend.agent.core.tools_for_auto_gather",
                return_value=tools,
            ), patch(
                "backend.agent.core.build_tool_manifest",
                return_value=[],
            ), patch(
                "backend.agent.core._save_context_cache",
            ) as save_mock:
                agen = _iter_gather_context_events(
                    session, streamer, out, pool, sid
                )
                async for _ in agen:
                    pass
            return save_mock

        save_mock = asyncio.run(run())
        registry.call_tool.assert_called_once()
        self.assertEqual(
            out["context"]["c.s.t"]["cold"],
            {"fresh": True},
        )
        self.assertTrue(out["context"][_MCP_GATHER_COMPLETE_KEY])
        self.assertGreaterEqual(save_mock.call_count, 2)
        last_ctx = save_mock.call_args_list[-1][0][2]
        self.assertTrue(last_ctx.get(_MCP_GATHER_COMPLETE_KEY))


if __name__ == "__main__":
    unittest.main()
