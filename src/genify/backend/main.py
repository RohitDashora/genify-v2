"""Genify V2 — FastAPI application entry point."""
import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from backend.db import init_db, seed_templates

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(name)s %(levelname)s %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)

STATIC_DIR = Path(__file__).parent.parent / "frontend" / "dist"


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup: init DB schema and seed templates."""
    logger.info("Genify V2 starting up")
    init_db()
    seed_templates()
    yield
    logger.info("Genify V2 shutting down")


app = FastAPI(
    title="Genify V2 (demo / reference)",
    description="Demo reference app: agentic metadata for Unity Catalog & Genie-style templates. Not for production.",
    version="2.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ---------------------------------------------------------------------------
# Register API routes — BEFORE the SPA fallback
# ---------------------------------------------------------------------------

_route_modules = [
    "backend.routes.health",
    "backend.routes.templates",
    "backend.routes.sessions",
    "backend.routes.completed",
    "backend.routes.catalog",
]

for module_path in _route_modules:
    try:
        import importlib
        mod = importlib.import_module(module_path)
        app.include_router(mod.router)
        logger.info(f"Registered route module: {module_path}")
    except Exception as e:
        logger.warning(f"Could not load route module {module_path}: {e}")

# ---------------------------------------------------------------------------
# Static files + SPA fallback (for built frontend)
# ---------------------------------------------------------------------------

if STATIC_DIR.exists() and (STATIC_DIR / "index.html").exists():
    app.mount("/assets", StaticFiles(directory=STATIC_DIR / "assets"), name="assets")

    @app.get("/{full_path:path}")
    async def spa_fallback(full_path: str):
        from fastapi.responses import FileResponse
        return FileResponse(STATIC_DIR / "index.html")

    logger.info(f"SPA fallback enabled from {STATIC_DIR}")
else:
    logger.info("No frontend build found — API-only mode")
