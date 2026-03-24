"""Smoke tests: retry from failed, DELETE session draft cleanup, PUT completed detach SQL."""
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


def _pool_with_session_row(row: dict):
    cur = MagicMock()

    def on_execute(query, params=None):
        s = str(query)
        if "DELETE FROM" in s and "sessions" in s and "completed_metadata" not in s:
            cur.rowcount = 1
        elif "DELETE FROM" in s and "completed_metadata" in s:
            cur.rowcount = 0
        else:
            cur.rowcount = 0

    cur.execute.side_effect = on_execute
    cur.fetchone.return_value = row

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


class TestRetrySectionFailed(unittest.TestCase):
    def setUp(self):
        for p in (
            patch("backend.main.init_db"),
            patch("backend.main.seed_templates"),
        ):
            p.start()
            self.addCleanup(p.stop)
        self.client = TestClient(app)

    def test_retry_200_when_failed_with_step(self):
        sid = uuid.uuid4()
        row = {
            "status": "failed",
            "current_step": 1,
            "plan": [{"section_key": "table_identity"}],
            "generated_yaml": "table_identity:\n  x: 1\n",
        }
        pool, cur, conn = _pool_with_session_row(row)
        with patch("backend.routes.sessions.remove_section_key", return_value="cleaned: yaml"):
            with patch("backend.routes.sessions._pool", return_value=pool):
                r = self.client.post(
                    f"/api/sessions/{sid}/retry-section",
                    headers={"X-Forwarded-Email": "dev@local"},
                )
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.json().get("ok"), True)
        conn.commit.assert_called_once()
        sql = " ".join(str(c[0][0]) for c in cur.execute.call_args_list if c[0])
        self.assertIn("status = 'executing'", sql)
        self.assertIn("error_message = NULL", sql)


class TestDeleteSessionDrafts(unittest.TestCase):
    def setUp(self):
        for p in (
            patch("backend.main.init_db"),
            patch("backend.main.seed_templates"),
        ):
            p.start()
            self.addCleanup(p.stop)
        self.client = TestClient(app)

    def test_delete_runs_draft_cleanup_before_session(self):
        sid = uuid.uuid4()
        pool, cur, conn = _pool_with_session_row({"id": sid})
        with patch("backend.routes.sessions._pool", return_value=pool):
            r = self.client.delete(
                f"/api/sessions/{sid}",
                headers={"X-Forwarded-Email": "dev@local"},
            )
        self.assertEqual(r.status_code, 200)
        calls = [str(c[0][0]) for c in cur.execute.call_args_list if c[0]]
        self.assertTrue(any("completed_metadata" in c and "DELETE" in c for c in calls))
        self.assertTrue(any("sessions" in c and "DELETE" in c for c in calls))
        idx_meta = next(i for i, c in enumerate(calls) if "completed_metadata" in c and "DELETE" in c)
        idx_sess = next(i for i, c in enumerate(calls) if "sessions" in c and "DELETE" in c and "completed" not in c)
        self.assertLess(idx_meta, idx_sess)


class TestCompletedPutDetach(unittest.TestCase):
    def setUp(self):
        for p in (
            patch("backend.main.init_db"),
            patch("backend.main.seed_templates"),
        ):
            p.start()
            self.addCleanup(p.stop)
        self.client = TestClient(app)

    def test_put_sets_session_id_null_and_clears_library_pointer(self):
        cid = uuid.uuid4()
        cur = MagicMock()
        cur.fetchone.side_effect = [
            {"template_type": "table_comment"},
            {
                "id": str(cid),
                "session_id": None,
                "yaml_content": "x: 1",
                "markdown_content": "# ok",
                "user_email": "dev@local",
                "template_type": "table_comment",
                "template_version": 1,
                "table_ref": {},
                "table_fqn": None,
                "version": 1,
                "artifact_status": "complete",
                "created_at": "2025-01-01T00:00:00Z",
                "updated_at": "2025-01-01T00:00:00Z",
            },
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

        with patch("backend.routes.completed._pool", return_value=pool):
            r = self.client.put(
                f"/api/completed/{cid}",
                headers={"X-Forwarded-Email": "dev@local"},
                json={"yaml_content": "y: 2"},
            )
        self.assertEqual(r.status_code, 200)
        sql = " ".join(str(c[0][0]) for c in cur.execute.call_args_list if c[0])
        self.assertIn("session_id = NULL", sql)
        self.assertIn("library_artifact_id = NULL", sql)


if __name__ == "__main__":
    unittest.main()
