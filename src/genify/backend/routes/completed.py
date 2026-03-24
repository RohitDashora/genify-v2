"""Completed metadata CRUD routes — list, get, edit YAML, delete."""
import logging
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from psycopg.rows import dict_row

from backend.agent.yaml_merge import format_yaml_for_persistence
from backend.config import get_config
from backend.db import get_pool, SCHEMA
from backend.middleware import get_current_user
from backend.models import CompletedListItem, CompletedResponse, CompletedUpdate

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/completed", tags=["completed"])


def _pool():
    pool = get_pool()
    if pool is None:
        raise HTTPException(503, detail="Database not available")
    return pool


@router.get("", response_model=list[CompletedListItem])
async def list_completed(
    template_type: str | None = None,
    user_email: str = Depends(get_current_user),
):
    """List completed metadata for the current user."""
    pool = _pool()
    clauses = ["user_email = %s"]
    params: list = [user_email]
    if template_type:
        clauses.append("template_type = %s")
        params.append(template_type)
    where = f"WHERE {' AND '.join(clauses)}"
    with pool.connection() as conn:
        with conn.cursor(row_factory=dict_row) as cur:
            cur.execute(
                f"SELECT id, template_type, table_ref, table_fqn, version, "
                f"artifact_status, created_at, updated_at "
                f"FROM {SCHEMA}.completed_metadata {where} "
                f"ORDER BY updated_at DESC",
                params,
            )
            return cur.fetchall()


@router.get("/{completed_id}", response_model=CompletedResponse)
async def get_completed(
    completed_id: UUID,
    user_email: str = Depends(get_current_user),
):
    """Get completed metadata with both YAML and Markdown content."""
    pool = _pool()
    with pool.connection() as conn:
        with conn.cursor(row_factory=dict_row) as cur:
            cur.execute(
                f"SELECT * FROM {SCHEMA}.completed_metadata "
                f"WHERE id = %s AND user_email = %s",
                (str(completed_id), user_email),
            )
            row = cur.fetchone()
    if not row:
        raise HTTPException(404, detail="Completed metadata not found")
    return row


@router.put("/{completed_id}", response_model=CompletedResponse)
async def update_completed(
    completed_id: UUID,
    body: CompletedUpdate,
    user_email: str = Depends(get_current_user),
):
    """Update YAML content. Backend re-generates markdown and stores both."""
    pool = _pool()

    from backend.llm.output_converter import safe_yaml_to_markdown

    cid = str(completed_id)
    ym = get_config().yaml_merge
    yaml_out, _, _ = format_yaml_for_persistence(
        body.yaml_content,
        enabled=ym.format_on_persist_enabled,
        dump_width=ym.format_dump_width,
        use_literal_blocks=ym.format_multiline_literals,
    )
    with pool.connection() as conn:
        with conn.cursor(row_factory=dict_row) as cur:
            cur.execute(
                f"SELECT template_type FROM {SCHEMA}.completed_metadata "
                f"WHERE id = %s AND user_email = %s",
                (cid, user_email),
            )
            existing = cur.fetchone()
            if not existing:
                raise HTTPException(404, detail="Completed metadata not found")

            markdown, _ok = safe_yaml_to_markdown(
                yaml_out,
                existing["template_type"],
            )
            cur.execute(
                f"UPDATE {SCHEMA}.completed_metadata "
                f"SET yaml_content = %s, markdown_content = %s, "
                f"session_id = NULL, updated_at = now() "
                f"WHERE id = %s AND user_email = %s "
                f"RETURNING *",
                (yaml_out, markdown, cid, user_email),
            )
            row = cur.fetchone()
            cur.execute(
                f"UPDATE {SCHEMA}.sessions SET library_artifact_id = NULL, updated_at = now() "
                f"WHERE library_artifact_id = %s::uuid",
                (cid,),
            )
        conn.commit()
    if not row:
        raise HTTPException(404, detail="Completed metadata not found")
    return row


@router.delete("/{completed_id}")
async def delete_completed(
    completed_id: UUID,
    user_email: str = Depends(get_current_user),
):
    """Delete completed metadata."""
    pool = _pool()
    with pool.connection() as conn:
        with conn.cursor(row_factory=dict_row) as cur:
            cur.execute(
                f"DELETE FROM {SCHEMA}.completed_metadata "
                f"WHERE id = %s AND user_email = %s",
                (str(completed_id), user_email),
            )
            if cur.rowcount == 0:
                raise HTTPException(404, detail="Completed metadata not found")
        conn.commit()
    return {"ok": True}
