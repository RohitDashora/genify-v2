"""Execute SQL via Databricks Statement Execution REST API."""
from __future__ import annotations

import time
from typing import Any, Optional

import requests

from server.client_factory import SqlSession


def _column_names_from_manifest(manifest: Any) -> list[str]:
    if not manifest or not isinstance(manifest, dict):
        return []
    schema = manifest.get("schema") or {}
    columns = schema.get("columns") or []
    return [c.get("name") or "" for c in columns if isinstance(c, dict)]


def _collect_rows(
    session: SqlSession,
    statement_id: str,
    first_result: Any,
) -> list[list[Any]]:
    """Collect all rows from first result and any subsequent chunks."""
    rows: list[list[Any]] = []
    result = first_result
    if result and isinstance(result, dict) and result.get("data_array"):
        rows.extend(result["data_array"])
    next_index = result.get("next_chunk_index") if isinstance(result, dict) else None
    while next_index is not None:
        url = f"{session.host}/api/2.0/sql/statements/{statement_id}/result/chunks/{next_index}"
        resp = requests.get(url, headers=session.get_headers(), timeout=30)
        resp.raise_for_status()
        chunk = resp.json()
        if chunk.get("data_array"):
            rows.extend(chunk["data_array"])
        next_index = chunk.get("next_chunk_index")
    return rows


def _fill_envelope(
    envelope: dict,
    session: SqlSession,
    body: dict,
    statement_id: str,
) -> None:
    """Extract columns/rows from response body into the envelope."""
    manifest = body.get("manifest") or {}
    result = body.get("result")
    columns = _column_names_from_manifest(manifest)
    rows = _collect_rows(session, statement_id, result) if result else []
    if not columns and result and result.get("data_array") and result["data_array"]:
        columns = [f"col_{i}" for i in range(len(result["data_array"][0]))]
    envelope["data"] = {
        "columns": columns,
        "rows": rows,
        "row_count": len(rows),
        "is_truncated": manifest.get("truncated", False),
    }


def execute_sql(
    session: SqlSession,
    statement: str,
    *,
    wait_timeout_seconds: int = 30,
    row_limit: Optional[int] = None,
) -> dict[str, Any]:
    """Execute SQL on the warehouse. Returns envelope: {status, warnings, errors, data}."""
    envelope = {
        "status": "ok",
        "warnings": [],
        "errors": [],
        "data": {"columns": [], "rows": [], "row_count": 0, "is_truncated": False},
    }

    payload = {
        "statement": statement,
        "warehouse_id": session.warehouse_id,
        "wait_timeout": f"{wait_timeout_seconds}s",
        "on_wait_timeout": "CONTINUE",
    }
    if row_limit is not None:
        payload["row_limit"] = row_limit

    url = f"{session.host}/api/2.0/sql/statements"
    try:
        resp = requests.post(
            url,
            json=payload,
            headers=session.get_headers(),
            timeout=wait_timeout_seconds + 10,
        )
        resp.raise_for_status()
        body = resp.json()
    except Exception as e:
        envelope["status"] = "error"
        envelope["errors"] = [str(e)]
        return envelope

    status = body.get("status") or {}
    state = status.get("state")

    if state == "FAILED":
        envelope["status"] = "error"
        err = status.get("error") or {}
        envelope["errors"] = [str(err.get("message") or state)]
        return envelope

    if state in ("CANCELED", "CLOSED"):
        envelope["status"] = "error"
        envelope["errors"] = [f"Statement ended with state: {state}"]
        return envelope

    if state == "SUCCEEDED":
        statement_id = body.get("statement_id")
        if statement_id:
            _fill_envelope(envelope, session, body, statement_id)
        return envelope

    # Poll for completion
    statement_id = body.get("statement_id")
    if not statement_id:
        envelope["status"] = "error"
        envelope["errors"] = ["No statement_id returned"]
        return envelope

    for _ in range(60):
        time.sleep(1)
        try:
            poll_resp = requests.get(
                f"{session.host}/api/2.0/sql/statements/{statement_id}",
                headers=session.get_headers(),
                timeout=15,
            )
            poll_resp.raise_for_status()
            poll = poll_resp.json()
        except Exception as e:
            envelope["status"] = "error"
            envelope["errors"] = [str(e)]
            return envelope
        st = poll.get("status") or {}
        sstate = st.get("state")
        if sstate == "SUCCEEDED":
            _fill_envelope(envelope, session, poll, statement_id)
            return envelope
        if sstate in ("FAILED", "CANCELED", "CLOSED"):
            envelope["status"] = "error"
            err = st.get("error") or {}
            envelope["errors"] = [str(err.get("message") or sstate)]
            return envelope

    envelope["status"] = "error"
    envelope["errors"] = ["Statement execution timed out"]
    return envelope
