"""
Pytest configuration and shared fixtures for all test suites.

Uses a separate test database (DATABASE_URL_TEST).
Tables are created via SQLAlchemy metadata (not Alembic) for speed.
Each test function gets a fresh, rolled-back transaction.

DB_AVAILABLE flag: if the test database is unreachable, all DB-dependent
tests are automatically skipped. Import/unit tests always run.
"""

import os
import sys
import pytest

# ── Load backend/.env so settings resolve before any app import ──────────────
from dotenv import load_dotenv
load_dotenv(os.path.join(os.path.dirname(__file__), "..", "backend", ".env"))

# Force testing mode
os.environ["APP_ENV"] = "testing"

# Make backend/ importable
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "backend"))

from collections.abc import Generator  # noqa: E402
from sqlalchemy import create_engine, text  # noqa: E402
from sqlalchemy.orm import sessionmaker, Session  # noqa: E402

from app.config import get_settings  # noqa: E402
from app.database import Base  # noqa: E402

# Import all models so Base.metadata knows about every table
import app.models  # noqa: F401, E402

settings = get_settings()


# ─────────────────────────────────────────────────────────────────────────────
# DB availability detection — runs once at session start
# ─────────────────────────────────────────────────────────────────────────────

def _check_db_reachable(url: str) -> bool:
    """Try to connect to the DB. Return True if successful."""
    try:
        engine = create_engine(url, pool_pre_ping=True, connect_args={"connect_timeout": 5})
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        engine.dispose()
        return True
    except Exception:
        return False


_db_url = settings.database_url_test or settings.database_url
DB_AVAILABLE = _check_db_reachable(_db_url)

# Pytest marker for skipping when no DB is present
requires_db = pytest.mark.skipif(
    not DB_AVAILABLE,
    reason=(
        "No live PostgreSQL available. "
        "Set DATABASE_URL_TEST in backend/.env to run DB tests."
    ),
)


# ─────────────────────────────────────────────────────────────────────────────
# Engine — created once per test session (only if DB is reachable)
# ─────────────────────────────────────────────────────────────────────────────

@pytest.fixture(scope="session")
def test_engine():
    if not DB_AVAILABLE:
        pytest.skip("No live PostgreSQL — skipping DB fixture.")
    engine = create_engine(_db_url, echo=False)
    Base.metadata.create_all(bind=engine)
    yield engine
    Base.metadata.drop_all(bind=engine)
    engine.dispose()


# ─────────────────────────────────────────────────────────────────────────────
# Session — each test gets a transaction that is rolled back
# ─────────────────────────────────────────────────────────────────────────────

@pytest.fixture
def db_session(test_engine) -> Generator[Session, None, None]:
    """
    Yield a database session rolled back after each test.
    Keeps tests isolated without truncating tables.
    """
    from sqlalchemy import event
    connection = test_engine.connect()
    transaction = connection.begin()
    
    # Start a nested transaction (SAVEPOINT)
    nested = connection.begin_nested()
    
    TestSession = sessionmaker(bind=connection, autocommit=False, autoflush=False)
    session = TestSession()
    
    @event.listens_for(session, "after_transaction_end")
    def end_savepoint(session, transaction):
        nonlocal nested
        if not nested.is_active:
            nested = connection.begin_nested()

    yield session
    
    session.close()
    transaction.rollback()
    connection.close()


# ─────────────────────────────────────────────────────────────────────────────
# FastAPI test client
# ─────────────────────────────────────────────────────────────────────────────

@pytest.fixture
def test_client(db_session):
    from fastapi.testclient import TestClient
    from app.main import app
    from app.database import get_db

    def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    client = TestClient(app, raise_server_exceptions=False)
    yield client
    app.dependency_overrides.clear()
