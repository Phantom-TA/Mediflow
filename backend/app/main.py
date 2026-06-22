"""
FastAPI application entry point.
"""

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import get_settings
from app.database import check_database_connection

settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup and shutdown logic."""
    # Startup
    db_ok = check_database_connection()
    if not db_ok:
        raise RuntimeError("Cannot connect to database on startup.")
    yield
    # Shutdown — nothing to clean up for sync engine


def create_app() -> FastAPI:
    app = FastAPI(
        title="MediFlow Voice Receptionist API",
        description=(
            "Backend tool layer for the MediFlow Voice AI Receptionist. "
            "All endpoints are called by Vapi during patient phone conversations."
        ),
        version=settings.app_version,
        docs_url="/docs",
        redoc_url="/redoc",
        lifespan=lifespan,
    )

    # ── CORS ──────────────────────────────────────────────────────────────
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.allowed_origins_list,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # ── Health check ──────────────────────────────────────────────────────
    @app.get("/health", tags=["system"])
    def health_check():
        db_ok = check_database_connection()
        return {
            "status": "healthy" if db_ok else "degraded",
            "database": "connected" if db_ok else "disconnected",
            "version": settings.app_version,
            "environment": settings.app_env,
        }

    # ── Routers (added in later phases) ──────────────────────────────────
    # from app.routers import tools
    # app.include_router(tools.router, prefix="/tools", tags=["tools"])

    return app


app = create_app()
