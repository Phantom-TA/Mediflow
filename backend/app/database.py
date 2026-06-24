"""
Database connection layer.

Provides:
- Synchronous SQLAlchemy engine + session (used by FastAPI routes)
- Base declarative class (used by all models)
- get_db() dependency for FastAPI
"""

from collections.abc import Generator

from sqlalchemy import create_engine, text
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.config import get_settings

settings = get_settings()


# ─────────────────────────────────────────────────────────────────────────────
# Declarative Base
# All SQLAlchemy models inherit from this.
# ─────────────────────────────────────────────────────────────────────────────

class Base(DeclarativeBase):
    pass


# ─────────────────────────────────────────────────────────────────────────────
# Engine
# ─────────────────────────────────────────────────────────────────────────────

def _build_engine(url: str):
    """Build a SQLAlchemy engine with production-grade pool settings."""
    return create_engine(
        url,
        pool_size=settings.db_pool_size,
        max_overflow=settings.db_max_overflow,
        pool_timeout=settings.db_pool_timeout,
        pool_recycle=settings.db_pool_recycle,
        pool_pre_ping=True,          # verify connection health before use
        echo=not settings.is_production,  # SQL logging in dev/test only
    )


engine = _build_engine(settings.effective_database_url)


# ─────────────────────────────────────────────────────────────────────────────
# Session Factory
# ─────────────────────────────────────────────────────────────────────────────

SessionLocal = sessionmaker(
    bind=engine,
    autocommit=False,
    autoflush=False,
    expire_on_commit=False,
)


# ─────────────────────────────────────────────────────────────────────────────
# FastAPI Dependency
# ─────────────────────────────────────────────────────────────────────────────

def get_db() -> Generator[Session, None, None]:
    """
    Yield a database session for use in FastAPI route dependencies.

    Usage:
        @router.post("/example")
        def example(db: Session = Depends(get_db)):
            ...
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


# ─────────────────────────────────────────────────────────────────────────────
# Health Check Helper
# ─────────────────────────────────────────────────────────────────────────────

def check_database_connection() -> bool:
    """
    Return True if the database is reachable, False otherwise.
    Used by the /health endpoint.
    """
    import sys
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        return True
    except Exception as e:
        print(f"Database connection verification failed: {e}", file=sys.stderr)
        return False


# ─────────────────────────────────────────────────────────────────────────────
# Schema Initialization Helper (for tests)
# ─────────────────────────────────────────────────────────────────────────────

def create_all_tables() -> None:
    """Create all tables. Used in test setup — production uses Alembic."""
    Base.metadata.create_all(bind=engine)


def drop_all_tables() -> None:
    """Drop all tables. Used in test teardown."""
    Base.metadata.drop_all(bind=engine)
