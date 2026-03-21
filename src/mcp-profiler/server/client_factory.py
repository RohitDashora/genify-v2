"""SQL session factory. Uses the app's service principal for auth."""
import os
from dataclasses import dataclass
from typing import Callable

import requests
from databricks.sdk import WorkspaceClient

_ws: WorkspaceClient | None = None


def _get_ws() -> WorkspaceClient:
    global _ws
    if _ws is None:
        _ws = WorkspaceClient()
    return _ws


@dataclass
class SqlSession:
    host: str
    warehouse_id: str
    get_headers: Callable[[], dict]


def get_session() -> SqlSession:
    """Get a SQL session with fresh auth from the service principal."""
    ws = _get_ws()
    wid = os.environ.get("WAREHOUSE_ID", "").strip()
    if not wid:
        raise RuntimeError("WAREHOUSE_ID environment variable not set")
    return SqlSession(
        host=ws.config.host.rstrip("/"),
        warehouse_id=wid,
        get_headers=ws.config.authenticate,
    )
