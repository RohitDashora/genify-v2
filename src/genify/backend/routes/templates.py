"""Template CRUD routes — add, update, delete, activate, clone, version."""
import logging
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from psycopg.rows import dict_row

from backend.db import get_pool, SCHEMA
from backend.middleware import get_current_user
from backend.models import (
    CloneRequest,
    TemplateCreate,
    TemplateListItem,
    TemplateResponse,
    TemplateUpdate,
)

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/templates", tags=["templates"])


def _pool():
    pool = get_pool()
    if pool is None:
        raise HTTPException(503, detail="Database not available")
    return pool


@router.get("", response_model=list[TemplateListItem])
async def list_templates(
    type: str | None = None,
    active_only: bool = False,
):
    """List templates, optionally filtered by type and active status."""
    pool = _pool()
    clauses, params = [], []
    if type:
        clauses.append("type = %s")
        params.append(type)
    if active_only:
        clauses.append("is_active = true")
    where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
    with pool.connection() as conn:
        with conn.cursor(row_factory=dict_row) as cur:
            cur.execute(
                f"SELECT id, type, version, name, is_active, created_by, "
                f"created_at, updated_at, notes "
                f"FROM {SCHEMA}.templates {where} ORDER BY type, version DESC",
                params,
            )
            return cur.fetchall()


@router.get("/{template_id}", response_model=TemplateResponse)
async def get_template(template_id: UUID):
    """Get a single template with full YAML content."""
    pool = _pool()
    with pool.connection() as conn:
        with conn.cursor(row_factory=dict_row) as cur:
            cur.execute(
                f"SELECT * FROM {SCHEMA}.templates WHERE id = %s",
                (str(template_id),),
            )
            row = cur.fetchone()
    if not row:
        raise HTTPException(404, detail="Template not found")
    return row


@router.post("", response_model=TemplateResponse, status_code=201)
async def create_template(
    body: TemplateCreate,
    user_email: str = Depends(get_current_user),
):
    """Create a new template version. Auto-assigns next version number."""
    pool = _pool()
    with pool.connection() as conn:
        with conn.cursor(row_factory=dict_row) as cur:
            cur.execute(
                f"SELECT COALESCE(MAX(version), 0) + 1 AS next_v "
                f"FROM {SCHEMA}.templates WHERE type = %s",
                (body.type,),
            )
            next_version = cur.fetchone()["next_v"]

            if body.activate:
                cur.execute(
                    f"UPDATE {SCHEMA}.templates SET is_active = false "
                    f"WHERE type = %s AND is_active = true",
                    (body.type,),
                )

            cur.execute(
                f"INSERT INTO {SCHEMA}.templates "
                f"(type, version, name, yaml_content, is_active, created_by, notes) "
                f"VALUES (%s, %s, %s, %s, %s, %s, %s) RETURNING *",
                (
                    body.type,
                    next_version,
                    body.name,
                    body.yaml_content,
                    body.activate,
                    user_email,
                    body.notes,
                ),
            )
            row = cur.fetchone()
        conn.commit()
    return row


@router.put("/{template_id}", response_model=TemplateResponse)
async def update_template(template_id: UUID, body: TemplateUpdate):
    """Update a template's content, name, or notes in-place."""
    pool = _pool()
    sets, params = [], []
    if body.yaml_content is not None:
        sets.append("yaml_content = %s")
        params.append(body.yaml_content)
    if body.name is not None:
        sets.append("name = %s")
        params.append(body.name)
    if body.notes is not None:
        sets.append("notes = %s")
        params.append(body.notes)
    if not sets:
        raise HTTPException(400, detail="No fields to update")

    sets.append("updated_at = now()")
    params.append(str(template_id))

    with pool.connection() as conn:
        with conn.cursor(row_factory=dict_row) as cur:
            # Check if any active sessions reference this template
            cur.execute(
                f"SELECT t.type, t.version FROM {SCHEMA}.templates t WHERE t.id = %s",
                (str(template_id),),
            )
            tpl = cur.fetchone()
            if not tpl:
                raise HTTPException(404, detail="Template not found")

            cur.execute(
                f"SELECT COUNT(*) AS cnt FROM {SCHEMA}.sessions "
                f"WHERE template_type = %s AND template_version = %s "
                f"AND status NOT IN ('complete', 'failed')",
                (tpl["type"], tpl["version"]),
            )
            if cur.fetchone()["cnt"] > 0:
                raise HTTPException(
                    409,
                    detail="Template is referenced by active sessions. Clone instead.",
                )

            cur.execute(
                f"UPDATE {SCHEMA}.templates SET {', '.join(sets)} "
                f"WHERE id = %s RETURNING *",
                params,
            )
            row = cur.fetchone()
        conn.commit()
    if not row:
        raise HTTPException(404, detail="Template not found")
    return row


@router.delete("/{template_id}")
async def delete_template(template_id: UUID, force: bool = False):
    """Delete a template version. 409 if referenced by sessions unless force=true."""
    pool = _pool()
    with pool.connection() as conn:
        with conn.cursor(row_factory=dict_row) as cur:
            cur.execute(
                f"SELECT type, version, is_active FROM {SCHEMA}.templates WHERE id = %s",
                (str(template_id),),
            )
            tpl = cur.fetchone()
            if not tpl:
                raise HTTPException(404, detail="Template not found")

            if not force:
                cur.execute(
                    f"SELECT COUNT(*) AS cnt FROM {SCHEMA}.sessions "
                    f"WHERE template_type = %s AND template_version = %s",
                    (tpl["type"], tpl["version"]),
                )
                if cur.fetchone()["cnt"] > 0:
                    raise HTTPException(
                        409,
                        detail="Template is referenced by sessions. Use ?force=true to detach and delete.",
                    )

            cur.execute(
                f"DELETE FROM {SCHEMA}.templates WHERE id = %s",
                (str(template_id),),
            )
        conn.commit()
    return {"ok": True}


@router.put("/{template_id}/activate")
async def activate_template(template_id: UUID):
    """Set this version as active for its type (deactivates others)."""
    pool = _pool()
    with pool.connection() as conn:
        with conn.cursor(row_factory=dict_row) as cur:
            cur.execute(
                f"SELECT type FROM {SCHEMA}.templates WHERE id = %s",
                (str(template_id),),
            )
            tpl = cur.fetchone()
            if not tpl:
                raise HTTPException(404, detail="Template not found")

            cur.execute(
                f"UPDATE {SCHEMA}.templates SET is_active = false "
                f"WHERE type = %s AND is_active = true",
                (tpl["type"],),
            )
            cur.execute(
                f"UPDATE {SCHEMA}.templates SET is_active = true, updated_at = now() "
                f"WHERE id = %s RETURNING *",
                (str(template_id),),
            )
            row = cur.fetchone()
        conn.commit()
    return row


@router.post("/{template_id}/clone", response_model=TemplateResponse, status_code=201)
async def clone_template(
    template_id: UUID,
    body: CloneRequest | None = None,
    user_email: str = Depends(get_current_user),
):
    """Clone a template as a new version (inactive draft)."""
    pool = _pool()
    with pool.connection() as conn:
        with conn.cursor(row_factory=dict_row) as cur:
            cur.execute(
                f"SELECT * FROM {SCHEMA}.templates WHERE id = %s",
                (str(template_id),),
            )
            source = cur.fetchone()
            if not source:
                raise HTTPException(404, detail="Template not found")

            cur.execute(
                f"SELECT COALESCE(MAX(version), 0) + 1 AS next_v "
                f"FROM {SCHEMA}.templates WHERE type = %s",
                (source["type"],),
            )
            next_version = cur.fetchone()["next_v"]

            notes = (body.notes if body and body.notes else
                     f"Cloned from v{source['version']}")
            cur.execute(
                f"INSERT INTO {SCHEMA}.templates "
                f"(type, version, name, yaml_content, is_active, created_by, notes) "
                f"VALUES (%s, %s, %s, %s, false, %s, %s) RETURNING *",
                (
                    source["type"],
                    next_version,
                    source["name"],
                    source["yaml_content"],
                    user_email,
                    notes,
                ),
            )
            row = cur.fetchone()
        conn.commit()
    return row
