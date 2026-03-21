"""Health check endpoint."""
import logging

from fastapi import APIRouter

from backend.db import get_pool
from backend.models import HealthResponse

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api", tags=["health"])


@router.get("/health", response_model=HealthResponse)
async def health_check():
    """Liveness and dependency check."""
    pool = get_pool()
    lakebase_ok = False
    if pool:
        try:
            with pool.connection() as conn:
                with conn.cursor() as cur:
                    cur.execute("SELECT 1")
            lakebase_ok = True
        except Exception:
            pass

    return HealthResponse(
        status="ok" if lakebase_ok else "degraded",
        lakebase=lakebase_ok,
        llm=True,
        mcp_servers={},
    )
