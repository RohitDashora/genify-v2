"""GET /api/sessions/{id}/completed — returns per-table + combined rows."""
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


def _make_pool(rows):
    """Build a mock pool that returns the given list of rows from fetchall."""
    cur = MagicMock()
    cur.fetchall.return_value = rows

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
    return pool, cur


class TestSessionCompleted(unittest.TestCase):
    def setUp(self):
        self._patches = [
            patch("backend.main.init_db"),
            patch("backend.main.seed_templates"),
        ]
        for p in self._patches:
            p.start()
        self.client = TestClient(app)

    def tearDown(self):
        for p in self._patches:
            p.stop()

    def test_returns_list_of_completed_rows(self):
        session_id = str(uuid.uuid4())
        combined_id = str(uuid.uuid4())
        per_table_id = str(uuid.uuid4())
        rows = [
            {
                "id": combined_id,
                "session_id": session_id,
                "user_email": "test@databricks.com",
                "template_type": "table_comment",
                "table_ref": {"catalog": "main", "schema": "sales"},
                "yaml_content": "combined: true",
                "markdown_content": "# Combined",
                "table_fqn": None,
                "version": 1,
                "created_at": "2025-01-01T00:00:00Z",
                "updated_at": "2025-01-01T00:00:00Z",
            },
            {
                "id": per_table_id,
                "session_id": session_id,
                "user_email": "test@databricks.com",
                "template_type": "table_comment",
                "table_ref": {"catalog": "main", "schema": "sales"},
                "yaml_content": "table: orders",
                "markdown_content": "# Orders",
                "table_fqn": "main.sales.orders",
                "version": 1,
                "created_at": "2025-01-01T00:00:00Z",
                "updated_at": "2025-01-01T00:00:00Z",
            },
        ]
        pool, _ = _make_pool(rows)

        with patch("backend.routes.sessions.get_pool", return_value=pool), \
             patch("backend.middleware.get_current_user", return_value="test@databricks.com"):
            resp = self.client.get(f"/api/sessions/{session_id}/completed")

        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(len(data), 2)
        self.assertIsNone(data[0]["table_fqn"])
        self.assertEqual(data[1]["table_fqn"], "main.sales.orders")

    def test_returns_empty_list_when_no_completed(self):
        session_id = str(uuid.uuid4())
        pool, _ = _make_pool([])

        with patch("backend.routes.sessions.get_pool", return_value=pool), \
             patch("backend.middleware.get_current_user", return_value="test@databricks.com"):
            resp = self.client.get(f"/api/sessions/{session_id}/completed")

        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json(), [])


if __name__ == "__main__":
    unittest.main()
