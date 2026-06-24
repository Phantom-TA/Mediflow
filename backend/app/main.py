"""
FastAPI application entry point.
"""

from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

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

    # ── Custom Error Handlers ─────────────────────────────────────────────
    @app.exception_handler(StarletteHTTPException)
    async def http_exception_handler(request, exc):
        if isinstance(exc.detail, dict):
            return JSONResponse(
                status_code=exc.status_code,
                content=exc.detail
            )
        return JSONResponse(
            status_code=exc.status_code,
            content={
                "success": False,
                "error_code": "UNAUTHORIZED" if exc.status_code == 401 else "INTERNAL_ERROR",
                "error_message": str(exc.detail),
                "data": None
            }
        )

    @app.exception_handler(RequestValidationError)
    async def validation_exception_handler(request, exc):
        errors = exc.errors()
        messages = []
        for err in errors:
            loc = " -> ".join(str(part) for part in err.get("loc", []))
            msg = err.get("msg", "Unknown error")
            messages.append(f"{loc}: {msg}")
        
        return JSONResponse(
            status_code=422,
            content={
                "success": False,
                "error_code": "VALIDATION_ERROR",
                "error_message": "Validation error: " + "; ".join(messages),
                "data": None
            }
        )

    # ── Health check ──────────────────────────────────────────────────────
    @app.api_route("/health", methods=["GET", "HEAD"], tags=["system"])
    def health_check(request: Request):
        db_ok = check_database_connection()
        if request.method == "HEAD":
            return Response(status_code=200)
        return {
            "status": "healthy" if db_ok else "degraded",
            "database": "connected" if db_ok else "disconnected",
            "version": settings.app_version,
            "environment": settings.app_env,
        }

    # ── Routers ───────────────────────────────────────────────────────────
    from app.routers import tools, vapi
    app.include_router(tools.router, prefix="/tools", tags=["tools"])
    app.include_router(vapi.router, prefix="/vapi", tags=["vapi"])

    return app


app = create_app()
