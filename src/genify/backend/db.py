"""Lakebase Autoscaling (PostgreSQL) connection pool, schema init, and template seeding.

Uses OAuthConnection to inject a fresh Databricks OAuth token on every
new physical connection. Tokens are generated via the Lakebase Autoscaling
API (w.postgres.generate_database_credential).

Environment variables (set automatically by Databricks Apps when a
postgres resource is configured):
    PGHOST, PGPORT, PGDATABASE, PGUSER, PGSSLMODE, PGAPPNAME
"""
import os
import logging
from contextlib import contextmanager
from pathlib import Path
from typing import Optional

import psycopg
import yaml
from psycopg import Connection
from psycopg.rows import dict_row
from psycopg_pool import ConnectionPool

logger = logging.getLogger(__name__)

_pool: Optional[ConnectionPool] = None

SCHEMA = "genify"
SEED_DIR = Path(__file__).parent.parent / "seed_templates"

# ---------------------------------------------------------------------------
# OAuth token helper
# ---------------------------------------------------------------------------

_workspace_client = None


def _get_workspace_client():
    global _workspace_client
    if _workspace_client is None:
        from databricks.sdk import WorkspaceClient
        _workspace_client = WorkspaceClient()
    return _workspace_client


def _get_oauth_token() -> Optional[str]:
    """Obtain a fresh OAuth access token for Lakebase Autoscaling.

    Uses w.postgres.generate_database_credential() which generates
    a short-lived token (1 hour) scoped to the app's postgres resource.
    Falls back to SDK header auth for local development.
    """
    try:
        ws = _get_workspace_client()
        try:
            cred = ws.postgres.generate_database_credential()
            return cred.token
        except Exception:
            pass
        headers = ws.config.authenticate()
        bearer = headers.get("Authorization", "")
        if bearer.startswith("Bearer "):
            return bearer[7:]
        logger.warning("Databricks SDK did not return a Bearer token")
        return None
    except Exception as e:
        logger.warning(f"OAuth token generation failed: {e}")
        return None


# ---------------------------------------------------------------------------
# OAuthConnection
# ---------------------------------------------------------------------------

class OAuthConnection(Connection):
    """psycopg3 Connection that injects a fresh OAuth token on connect."""

    @classmethod
    def connect(cls, conninfo: str = "", *, autocommit: bool = False, **kwargs):
        token = _get_oauth_token()
        if token:
            kwargs["password"] = token
        return super().connect(conninfo, autocommit=autocommit, **kwargs)


# ---------------------------------------------------------------------------
# Pool singleton
# ---------------------------------------------------------------------------

def _build_conninfo() -> str:
    host = os.getenv("PGHOST", "")
    port = os.getenv("PGPORT", "5432")
    dbname = os.getenv("PGDATABASE", "postgres")
    user = os.getenv("PGUSER", "")
    sslmode = os.getenv("PGSSLMODE", "require")
    appname = os.getenv("PGAPPNAME", "genify")
    return (
        f"host={host} port={port} dbname={dbname} "
        f"user={user} sslmode={sslmode} application_name={appname}"
    )


def get_pool() -> Optional[ConnectionPool]:
    """Return the singleton ConnectionPool. None if PGHOST is not set."""
    global _pool
    if _pool is not None:
        return _pool
    if not os.getenv("PGHOST"):
        logger.info("PGHOST not set — Lakebase pool will not be created")
        return None
    conninfo = _build_conninfo()
    logger.info(f"Creating Lakebase connection pool")
    try:
        from backend.config import get_config
        pool_size = get_config().lakebase.pool_size

        _pool = ConnectionPool(
            conninfo=conninfo,
            connection_class=OAuthConnection,
            min_size=min(2, pool_size),
            max_size=pool_size,
            open=True,
            kwargs={"autocommit": False, "row_factory": dict_row},
        )
        logger.info("Lakebase connection pool created successfully")
        return _pool
    except Exception as e:
        logger.error(f"Failed to create Lakebase pool: {e}", exc_info=True)
        return None


# ---------------------------------------------------------------------------
# Convenience context managers
# ---------------------------------------------------------------------------

@contextmanager
def get_db():
    """Yield a psycopg Connection from the pool."""
    pool = get_pool()
    if pool is None:
        raise RuntimeError("Lakebase connection pool is not available")
    with pool.connection() as conn:
        yield conn


@contextmanager
def get_cursor():
    """Yield a psycopg Cursor with dict_row factory."""
    with get_db() as conn:
        with conn.cursor(row_factory=dict_row) as cur:
            yield cur


# ---------------------------------------------------------------------------
# Schema initialisation
# ---------------------------------------------------------------------------

_DDL = f"""
CREATE SCHEMA IF NOT EXISTS {SCHEMA};

CREATE TABLE IF NOT EXISTS {SCHEMA}.templates (
    id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    type          VARCHAR(50)  NOT NULL,
    version       INTEGER      NOT NULL DEFAULT 1,
    name          VARCHAR(255) NOT NULL,
    yaml_content  TEXT         NOT NULL,
    is_active     BOOLEAN      DEFAULT false,
    created_by    VARCHAR(255) NOT NULL,
    created_at    TIMESTAMPTZ  DEFAULT now(),
    updated_at    TIMESTAMPTZ  DEFAULT now(),
    notes         TEXT,
    UNIQUE (type, version)
);

CREATE TABLE IF NOT EXISTS {SCHEMA}.sessions (
    id               UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_email       VARCHAR(255) NOT NULL,
    template_type    VARCHAR(50)  NOT NULL,
    template_version INTEGER      NOT NULL,
    mode             VARCHAR(20)  NOT NULL CHECK (mode IN ('hands_off', 'interactive')),
    status           VARCHAR(30)  NOT NULL DEFAULT 'created',
    table_ref        JSONB        NOT NULL,
    plan             JSONB,
    current_step     INTEGER      DEFAULT 0,
    generated_yaml   TEXT         DEFAULT '',
    conversation     JSONB        DEFAULT '[]'::jsonb,
    context_cache    JSONB        DEFAULT '{{}}'::jsonb,
    output_format    VARCHAR(20)  DEFAULT 'yaml',
    error_message    TEXT,
    created_at       TIMESTAMPTZ  DEFAULT now(),
    updated_at       TIMESTAMPTZ  DEFAULT now(),
    completed_at     TIMESTAMPTZ,
    pending_question JSONB
);

CREATE INDEX IF NOT EXISTS idx_sessions_user
    ON {SCHEMA}.sessions(user_email);
CREATE INDEX IF NOT EXISTS idx_sessions_status
    ON {SCHEMA}.sessions(status);

CREATE TABLE IF NOT EXISTS {SCHEMA}.completed_metadata (
    id               UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    session_id       UUID REFERENCES {SCHEMA}.sessions(id) ON DELETE SET NULL,
    user_email       VARCHAR(255) NOT NULL,
    template_type    VARCHAR(50)  NOT NULL,
    table_ref        JSONB        NOT NULL,
    yaml_content     TEXT         NOT NULL,
    markdown_content TEXT,
    table_fqn        VARCHAR(512),
    version          INTEGER      DEFAULT 1,
    created_at       TIMESTAMPTZ  DEFAULT now(),
    updated_at       TIMESTAMPTZ  DEFAULT now()
);

ALTER TABLE {SCHEMA}.completed_metadata ADD COLUMN IF NOT EXISTS table_fqn VARCHAR(512);
"""


def init_db() -> None:
    """Create the genify schema and all tables. Idempotent."""
    pool = get_pool()
    if pool is None:
        logger.info("Skipping DB init — pool not available")
        return
    try:
        with pool.connection() as conn:
            with conn.cursor() as cur:
                for statement in _DDL.strip().split(";"):
                    statement = statement.strip()
                    if statement:
                        try:
                            cur.execute(statement)
                        except Exception as e:
                            conn.rollback()
                            logger.debug(f"DDL statement skipped: {e}")
            conn.commit()
        # Existing workspaces: add column if missing (CREATE TABLE IF NOT EXISTS skips new cols).
        try:
            with pool.connection() as conn:
                with conn.cursor() as cur:
                    cur.execute(
                        f"ALTER TABLE {SCHEMA}.sessions "
                        f"ADD COLUMN IF NOT EXISTS pending_question JSONB"
                    )
                conn.commit()
        except Exception as e:
            logger.warning(f"pending_question migration: {e}")
        logger.info("Genify schema initialisation complete")
    except Exception as e:
        logger.error(f"DB init failed: {e}", exc_info=True)


# ---------------------------------------------------------------------------
# Template seeding
# ---------------------------------------------------------------------------

def seed_templates() -> None:
    """Seed default templates from seed_templates/ if the table is empty."""
    pool = get_pool()
    if pool is None:
        return
    try:
        with pool.connection() as conn:
            with conn.cursor(row_factory=dict_row) as cur:
                cur.execute(f"SELECT COUNT(*) AS cnt FROM {SCHEMA}.templates")
                row = cur.fetchone()
                if row and row["cnt"] > 0:
                    logger.info(f"Templates table has {row['cnt']} rows — skipping seed")
                    return

                for seed_file in sorted(SEED_DIR.glob("*.yaml")):
                    logger.info(f"Seeding template from {seed_file.name}")
                    with open(seed_file) as f:
                        content = yaml.safe_load(f)

                    meta = content.get("_meta", {})
                    tpl_type = meta.get("type", seed_file.stem.rsplit("_v", 1)[0])
                    tpl_name = meta.get("name", seed_file.stem)
                    tpl_version = int(meta.get("version", 1))
                    tpl_notes = meta.get("notes", "")

                    with open(seed_file) as f:
                        yaml_text = f.read()

                    cur.execute(
                        f"""
                        INSERT INTO {SCHEMA}.templates
                            (type, version, name, yaml_content, is_active, created_by, notes)
                        VALUES (%s, %s, %s, %s, true, %s, %s)
                        ON CONFLICT (type, version) DO NOTHING
                        """,
                        (tpl_type, tpl_version, tpl_name, yaml_text, "system", tpl_notes),
                    )
            conn.commit()
        logger.info("Template seeding complete")
    except Exception as e:
        logger.error(f"Template seeding failed: {e}", exc_info=True)
