"""Session CRUD routes + SSE streaming endpoint."""
import json
import logging
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request
from psycopg.rows import dict_row
from sse_starlette.sse import EventSourceResponse

from backend.db import get_pool, SCHEMA
from backend.middleware import get_current_user
from backend.agent.yaml_merge import remove_section_key

from backend.models import (
    AnswerRequest,
    CompletedResponse,
    SessionCreate,
    SessionListItem,
    SessionResponse,
)

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/sessions", tags=["sessions"])


def _pool():
    pool = get_pool()
    if pool is None:
        raise HTTPException(503, detail="Database not available")
    return pool


@router.post("", response_model=dict, status_code=201)
async def create_session(
    body: SessionCreate,
    user_email: str = Depends(get_current_user),
):
    """Create a new agent session. Returns session id."""
    pool = _pool()

    # Genie is always interactive
    mode = body.mode
    if body.template_type == "genie":
        mode = "interactive"

    with pool.connection() as conn:
        with conn.cursor(row_factory=dict_row) as cur:
            # Look up active template version
            cur.execute(
                f"SELECT version FROM {SCHEMA}.templates "
                f"WHERE type = %s AND is_active = true",
                (body.template_type,),
            )
            tpl = cur.fetchone()
            if not tpl:
                raise HTTPException(
                    404,
                    detail=f"No active template for type '{body.template_type}'",
                )

            table_ref = body.table_ref.model_dump(by_alias=True)
            cur.execute(
                f"INSERT INTO {SCHEMA}.sessions "
                f"(user_email, template_type, template_version, mode, "
                f" table_ref, output_format) "
                f"VALUES (%s, %s, %s, %s, %s, %s) "
                f"RETURNING id, status",
                (
                    user_email,
                    body.template_type,
                    tpl["version"],
                    mode,
                    json.dumps(table_ref),
                    body.output_format,
                ),
            )
            row = cur.fetchone()
        conn.commit()
    return {"session_id": str(row["id"]), "status": row["status"]}


@router.get("", response_model=list[SessionListItem])
async def list_sessions(
    status: str | None = None,
    user_email: str = Depends(get_current_user),
):
    """List sessions for the current user, optionally filtered by status."""
    pool = _pool()
    clauses = ["user_email = %s"]
    params: list = [user_email]
    if status and status != "all":
        clauses.append("status = %s")
        params.append(status)
    where = f"WHERE {' AND '.join(clauses)}"
    with pool.connection() as conn:
        with conn.cursor(row_factory=dict_row) as cur:
            cur.execute(
                f"SELECT id, template_type, mode, status, table_ref, "
                f"current_step, created_at, updated_at, completed_at "
                f"FROM {SCHEMA}.sessions {where} ORDER BY updated_at DESC",
                params,
            )
            return cur.fetchall()


@router.get("/{session_id}/completed", response_model=list[CompletedResponse])
async def get_session_completed(
    session_id: UUID,
    user_email: str = Depends(get_current_user),
):
    """Get completed metadata rows for a session (per-table + combined)."""
    pool = _pool()
    with pool.connection() as conn:
        with conn.cursor(row_factory=dict_row) as cur:
            cur.execute(
                f"SELECT * FROM {SCHEMA}.completed_metadata "
                f"WHERE session_id = %s AND user_email = %s "
                f"ORDER BY table_fqn NULLS FIRST",
                (str(session_id), user_email),
            )
            return cur.fetchall()


@router.get("/{session_id}", response_model=SessionResponse)
async def get_session(session_id: UUID, user_email: str = Depends(get_current_user)):
    """Get full session state (for resume)."""
    pool = _pool()
    with pool.connection() as conn:
        with conn.cursor(row_factory=dict_row) as cur:
            cur.execute(
                f"SELECT * FROM {SCHEMA}.sessions "
                f"WHERE id = %s AND user_email = %s",
                (str(session_id), user_email),
            )
            row = cur.fetchone()
    if not row:
        raise HTTPException(404, detail="Session not found")
    return row


@router.get("/{session_id}/stream")
async def stream_session(
    session_id: UUID,
    request: Request,
    user_email: str = Depends(get_current_user),
):
    """SSE stream — the main interaction channel.

    The agent loop runs here: gathers context, plans, executes,
    and streams events back to the client.
    """
    pool = _pool()

    with pool.connection() as conn:
        with conn.cursor(row_factory=dict_row) as cur:
            cur.execute(
                f"SELECT id FROM {SCHEMA}.sessions "
                f"WHERE id = %s AND user_email = %s",
                (str(session_id), user_email),
            )
            if not cur.fetchone():
                raise HTTPException(404, detail="Session not found")

    from backend.agent.core import run_agent
    return EventSourceResponse(run_agent(str(session_id), pool))


@router.post("/{session_id}/answer")
async def answer_question(
    session_id: UUID,
    body: AnswerRequest,
    user_email: str = Depends(get_current_user),
):
    """Submit user answer in interactive mode. Agent resumes on SSE reconnect."""
    pool = _pool()
    with pool.connection() as conn:
        with conn.cursor(row_factory=dict_row) as cur:
            cur.execute(
                f"SELECT status, conversation FROM {SCHEMA}.sessions "
                f"WHERE id = %s AND user_email = %s",
                (str(session_id), user_email),
            )
            row = cur.fetchone()
            if not row:
                raise HTTPException(404, detail="Session not found")
            if row["status"] != "waiting_for_user":
                raise HTTPException(
                    409,
                    detail={
                        "message": (
                            f"Session is '{row['status']}', not waiting for answer"
                        ),
                        "code": "not_waiting_for_user",
                    },
                )

            conversation = row["conversation"] or []
            if (
                conversation
                and isinstance(conversation[-1], dict)
                and conversation[-1].get("role") == "user"
            ):
                raise HTTPException(
                    409,
                    detail={
                        "message": (
                            "An answer is already queued. Open or reconnect the live "
                            "stream so the agent can process it before sending another."
                        ),
                        "code": "answer_already_queued",
                    },
                )

            conversation.append({
                "role": "user",
                "content": body.answer,
            })

            # Stay waiting_for_user until run_agent consumes the answer (incorporate path).
            cur.execute(
                f"UPDATE {SCHEMA}.sessions "
                f"SET conversation = %s, status = 'waiting_for_user', updated_at = now() "
                f"WHERE id = %s",
                (json.dumps(conversation), str(session_id)),
            )
        conn.commit()
    return {"ok": True}


@router.post("/{session_id}/retry-section")
async def retry_section(
    session_id: UUID,
    user_email: str = Depends(get_current_user),
):
    """Drop the last merged section and re-run that step on the next SSE connection.

    Decrements ``current_step`` and removes the previous step's ``section_key`` from
    ``generated_yaml``. Idempotent if the session is already at step 0.
    """
    pool = _pool()
    with pool.connection() as conn:
        with conn.cursor(row_factory=dict_row) as cur:
            cur.execute(
                f"SELECT * FROM {SCHEMA}.sessions "
                f"WHERE id = %s AND user_email = %s",
                (str(session_id), user_email),
            )
            row = cur.fetchone()
            if not row:
                raise HTTPException(404, detail="Session not found")
            st = row.get("status") or ""
            if st not in ("executing", "waiting_for_user"):
                raise HTTPException(
                    409,
                    detail={
                        "code": "retry_not_allowed",
                        "message": f"Session status is '{st}', cannot retry a section",
                    },
                )
            cs = int(row.get("current_step") or 0)
            plan = row.get("plan")
            if isinstance(plan, str):
                plan = json.loads(plan)
            plan = plan or []
            if st == "waiting_for_user":
                cur.execute(
                    f"UPDATE {SCHEMA}.sessions SET "
                    f"pending_section_yaml = '', pending_question = NULL, "
                    f"status = 'executing', updated_at = now() WHERE id = %s",
                    (str(session_id),),
                )
                conn.commit()
                return {"ok": True, "cleared_pending": True}

            if cs < 1:
                raise HTTPException(
                    400,
                    detail={"code": "nothing_to_retry", "message": "No completed section to roll back"},
                )
            idx = cs - 1
            if idx >= len(plan):
                raise HTTPException(400, detail="Plan index out of range")
            section_key = plan[idx].get("section_key", "")
            if not section_key:
                raise HTTPException(400, detail="Invalid plan step")
            new_yaml = remove_section_key(row.get("generated_yaml") or "", section_key)
            cur.execute(
                f"UPDATE {SCHEMA}.sessions SET "
                f"generated_yaml = %s, current_step = %s, "
                f"pending_section_yaml = '', pending_question = NULL, "
                f"status = 'executing', updated_at = now() WHERE id = %s",
                (new_yaml, idx, str(session_id)),
            )
        conn.commit()
    return {"ok": True, "current_step": idx}


@router.delete("/{session_id}")
async def delete_session(
    session_id: UUID,
    user_email: str = Depends(get_current_user),
):
    """Delete a session."""
    pool = _pool()
    with pool.connection() as conn:
        with conn.cursor(row_factory=dict_row) as cur:
            cur.execute(
                f"DELETE FROM {SCHEMA}.sessions "
                f"WHERE id = %s AND user_email = %s",
                (str(session_id), user_email),
            )
            if cur.rowcount == 0:
                raise HTTPException(404, detail="Session not found")
        conn.commit()
    return {"ok": True}
