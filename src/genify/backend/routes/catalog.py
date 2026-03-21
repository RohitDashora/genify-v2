"""Catalog browsing routes for the UI table picker.

Uses direct SQL against information_schema via the Databricks SQL connector.
Warehouse ID comes from the WAREHOUSE_ID env var (injected by resource binding).
"""
import logging
import os

from fastapi import APIRouter, HTTPException

from backend.models import CatalogListResponse, SchemaListResponse, TableListResponse

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/catalog", tags=["catalog"])


def _get_sql_connection():
    """Get a Databricks SQL connection for catalog queries."""
    try:
        from databricks.sql import connect
        from databricks.sdk import WorkspaceClient

        ws = WorkspaceClient()
        host = ws.config.host
        token = ws.config.authenticate().get("Authorization", "").replace("Bearer ", "")

        warehouse_id = os.environ.get("WAREHOUSE_ID", "").strip()
        if not warehouse_id:
            logger.error("WAREHOUSE_ID environment variable not set")
            return None

        return connect(
            server_hostname=host.replace("https://", ""),
            http_path=f"/sql/1.0/warehouses/{warehouse_id}",
            access_token=token,
        )
    except Exception as e:
        logger.error(f"SQL connection failed: {e}", exc_info=True)
        return None


@router.get("/catalogs", response_model=CatalogListResponse)
async def list_catalogs():
    conn = _get_sql_connection()
    if not conn:
        raise HTTPException(503, detail="SQL warehouse not available")
    try:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT catalog_name FROM system.information_schema.catalogs "
                "WHERE catalog_name NOT IN ('system', '__databricks_internal') "
                "ORDER BY catalog_name"
            )
            catalogs = [row[0] for row in cur.fetchall()]
        return CatalogListResponse(catalogs=catalogs)
    finally:
        conn.close()


@router.get("/{catalog}/schemas", response_model=SchemaListResponse)
async def list_schemas(catalog: str):
    conn = _get_sql_connection()
    if not conn:
        raise HTTPException(503, detail="SQL warehouse not available")
    try:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT schema_name FROM system.information_schema.schemata "
                "WHERE catalog_name = ? "
                "AND schema_name NOT IN ('information_schema', 'default') "
                "ORDER BY schema_name",
                (catalog,),
            )
            schemas = [row[0] for row in cur.fetchall()]
        return SchemaListResponse(schemas=schemas)
    finally:
        conn.close()


@router.get("/{catalog}/{schema}/tables", response_model=TableListResponse)
async def list_tables(catalog: str, schema: str):
    conn = _get_sql_connection()
    if not conn:
        raise HTTPException(503, detail="SQL warehouse not available")
    try:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT table_name, table_type, comment "
                "FROM system.information_schema.tables "
                "WHERE table_catalog = ? AND table_schema = ? "
                "ORDER BY table_name",
                (catalog, schema),
            )
            tables = [
                {"name": row[0], "type": row[1], "comment": row[2]}
                for row in cur.fetchall()
            ]
        return TableListResponse(tables=tables)
    finally:
        conn.close()
