"""context_cache persistence: empty gather must not UPDATE sessions to {}."""
from __future__ import annotations

import json
import sys
import unittest
import uuid
from contextlib import contextmanager
from pathlib import Path
from unittest.mock import MagicMock

GENIFY_ROOT = Path(__file__).resolve().parents[1] / "src" / "genify"
if str(GENIFY_ROOT) not in sys.path:
    sys.path.insert(0, str(GENIFY_ROOT))

from backend.agent.core import _save_context_cache  # noqa: E402


def _pool_that_tracks_execute():
    """Pool whose connection runs UPDATE; we assert execute was / was not called."""
    executed = {"calls": 0}

    @contextmanager
    def connection_cm():
        cur = MagicMock()

        def execute(sql, params=None):
            executed["calls"] += 1
            if params and isinstance(params[0], str):
                payload = json.loads(params[0])
                executed["last_payload"] = payload

        cur.execute.side_effect = execute
        conn = MagicMock()
        conn.commit = MagicMock()
        ctx = MagicMock()
        ctx.__enter__ = lambda *_: cur
        ctx.__exit__ = lambda *_: None
        conn.cursor.return_value = ctx
        yield conn

    pool = MagicMock()
    pool.connection = connection_cm
    return pool, executed


class TestSaveContextCache(unittest.TestCase):
    def test_skips_empty_dict(self):
        pool, executed = _pool_that_tracks_execute()
        sid = str(uuid.uuid4())
        _save_context_cache(pool, sid, {})
        self.assertEqual(executed["calls"], 0)

    def test_skips_non_dict(self):
        pool, executed = _pool_that_tracks_execute()
        sid = str(uuid.uuid4())
        _save_context_cache(pool, sid, None)  # type: ignore[arg-type]
        self.assertEqual(executed["calls"], 0)

    def test_persists_manifest_only(self):
        pool, executed = _pool_that_tracks_execute()
        sid = str(uuid.uuid4())
        payload = {"_mcp_tool_manifest": [{"name": "x", "server": "s"}]}
        _save_context_cache(pool, sid, payload)
        self.assertEqual(executed["calls"], 1)
        self.assertEqual(executed["last_payload"], payload)

    def test_persists_table_key(self):
        pool, executed = _pool_that_tracks_execute()
        sid = str(uuid.uuid4())
        payload = {"cat.sch.t": {"profile_table": {"status": "ok"}}}
        _save_context_cache(pool, sid, payload)
        self.assertEqual(executed["calls"], 1)
        self.assertEqual(
            executed["last_payload"]["cat.sch.t"]["profile_table"]["status"],
            "ok",
        )


if __name__ == "__main__":
    unittest.main()
