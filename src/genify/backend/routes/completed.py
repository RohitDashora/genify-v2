"""Completed metadata CRUD routes — list, get, edit YAML, delete."""
import logging
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from psycopg.rows import dict_row

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


def _yaml_to_markdown(yaml_content: str, template_type: str = "table_comment") -> str:
    """Convert YAML to markdown using the output converter."""
    from backend.llm.output_converter import yaml_to_markdown
    return yaml_to_markdown(yaml_content, template_type)


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
                f"created_at, updated_at "
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

    # Look up template_type for proper markdown conversion
    with pool.connection() as conn:
        with conn.cursor(row_factory=dict_row) as cur:
            cur.execute(
                f"SELECT template_type FROM {SCHEMA}.completed_metadata "
                f"WHERE id = %s AND user_email = %s",
                (str(completed_id), user_email),
            )
            existing = cur.fetchone()
    if not existing:
        raise HTTPException(404, detail="Completed metadata not found")

    markdown = _yaml_to_markdown(body.yaml_content, existing["template_type"])
    with pool.connection() as conn:
        with conn.cursor(row_factory=dict_row) as cur:
            cur.execute(
                f"UPDATE {SCHEMA}.completed_metadata "
                f"SET yaml_content = %s, markdown_content = %s, updated_at = now() "
                f"WHERE id = %s AND user_email = %s "
                f"RETURNING *",
                (body.yaml_content, markdown, str(completed_id), user_email),
            )
            row = cur.fetchone()
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
