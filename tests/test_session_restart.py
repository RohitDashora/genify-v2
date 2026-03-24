"""POST /api/sessions/{id}/restart — resets session and removes draft Library rows."""
from __future__ import annotations

import sys
import unittest
import uuid
from contextlib import contextmanager
from pathlib import Path
from unittest.mock import MagicMock, patch

from fastapi.testclient import TestClient

GENIFY_ROOT = Path(__file__).resolve().parents[1] / "src" / "genify"
if str(GENIFY_ROOT) not in sys.path:
    sys.path.insert(0, str(GENIFY_ROOT))

from backend.main import app  # noqa: E402


def _make_pool_session_exists():
    cur = MagicMock()
    cur.execute.return_value = None
    cur.fetchone.side_effect = [
        {"id": uuid.uuid4()},  # SELECT session exists
        None,
    ]

    conn = MagicMock()
    conn.commit = MagicMock()
    ctx = MagicMock()
    ctx.__enter__ = lambda *_: cur
    ctx.__exit__ = lambda *_: None
    conn.cursor.return_value = ctx

    @contextmanager
    def connection_cm():
        yield conn

    pool = MagicMock()
    pool.connection = connection_cm
    return pool, cur, conn


class TestSessionRestart(unittest.TestCase):
    def setUp(self):
        for p in (
            patch("backend.main.init_db"),
            patch("backend.main.seed_templates"),
        ):
            p.start()
            self.addCleanup(p.stop)
        self.client = TestClient(app)

    def test_restart_200_runs_delete_and_update(self):
        sid = uuid.uuid4()
        pool, cur, conn = _make_pool_session_exists()
        with patch("backend.routes.sessions._pool", return_value=pool):
            r = self.client.post(
                f"/api/sessions/{sid}/restart",
                headers={"X-Forwarded-Email": "dev@local"},
            )
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.json(), {"ok": True})
        conn.commit.assert_called_once()
        sql_calls = " ".join(str(c[0][0]) for c in cur.execute.call_args_list if c[0])
        self.assertIn("DELETE", sql_calls)
        self.assertIn("completed_metadata", sql_calls)
        self.assertIn("library_artifact_id = NULL", sql_calls)
        self.assertIn("context_cache", sql_calls)

    def test_restart_404_when_missing(self):
        sid = uuid.uuid4()
        cur = MagicMock()
        cur.fetchone.return_value = None
        conn = MagicMock()
        ctx = MagicMock()
        ctx.__enter__ = lambda *_: cur
        ctx.__exit__ = lambda *_: None
        conn.cursor.return_value = ctx

        @contextmanager
        def connection_cm():
            yield conn

        pool = MagicMock()
        pool.connection = connection_cm
        with patch("backend.routes.sessions._pool", return_value=pool):
            r = self.client.post(
                f"/api/sessions/{sid}/restart",
                headers={"X-Forwarded-Email": "dev@local"},
            )
        self.assertEqual(r.status_code, 404)


if __name__ == "__main__":
    unittest.main()
