"""POST /api/sessions/{id}/answer — 409 vs 200 with mocked Lakebase pool."""
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


def _make_pool(status: str, conversation: list | None):
    row = {
        "status": status,
        "conversation": conversation or [],
    }
    cur = MagicMock()
    cur.execute.return_value = None
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


class TestGenifySessionAnswer(unittest.TestCase):
    def setUp(self):
        # Lifespan runs on TestClient enter; avoid real Lakebase during startup.
        for p in (
            patch("backend.main.init_db"),
            patch("backend.main.seed_templates"),
        ):
            p.start()
            self.addCleanup(p.stop)
        self.client = TestClient(app)

    def test_answer_409_when_not_waiting_for_user(self):
        sid = uuid.uuid4()
        pool, _, _ = _make_pool("executing", [])
        with patch("backend.routes.sessions._pool", return_value=pool):
            r = self.client.post(
                f"/api/sessions/{sid}/answer",
                json={"answer": "hello"},
                headers={"X-Forwarded-Email": "dev@local"},
            )
        self.assertEqual(r.status_code, 409)
        body = r.json()
        self.assertEqual(body["detail"]["code"], "not_waiting_for_user")
        self.assertIn("message", body["detail"])

    def test_answer_200_when_waiting_for_user(self):
        sid = uuid.uuid4()
        pool, cur, conn = _make_pool(
            "waiting_for_user",
            [{"role": "assistant", "content": "What?"}],
        )
        with patch("backend.routes.sessions._pool", return_value=pool):
            r = self.client.post(
                f"/api/sessions/{sid}/answer",
                json={"answer": "my answer"},
                headers={"X-Forwarded-Email": "dev@local"},
            )
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.json(), {"ok": True})
        conn.commit.assert_called_once()
        # Must stay waiting until run_agent consumes the answer (incorporate path).
        sql_calls = [str(c[0][0]) for c in cur.execute.call_args_list if c[0]]
        self.assertTrue(any("waiting_for_user" in s for s in sql_calls))

    def test_answer_409_when_answer_already_queued(self):
        sid = uuid.uuid4()
        pool, _, _ = _make_pool(
            "waiting_for_user",
            [
                {"role": "assistant", "content": "What?"},
                {"role": "user", "content": "first answer"},
            ],
        )
        with patch("backend.routes.sessions._pool", return_value=pool):
            r = self.client.post(
                f"/api/sessions/{sid}/answer",
                json={"answer": "second"},
                headers={"X-Forwarded-Email": "dev@local"},
            )
        self.assertEqual(r.status_code, 409)
        self.assertEqual(r.json()["detail"]["code"], "answer_already_queued")


if __name__ == "__main__":
    unittest.main()
