"""
Alembic environment configuration.

Reads DATABASE_URL from app settings.
Imports all models so autogenerate can detect schema changes.
"""

import os
import sys
from logging.config import fileConfig

from sqlalchemy import engine_from_config, pool
from alembic import context

# ── Make app importable from the backend/ directory ───────────────────────────
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

# ── Import app settings and Base ──────────────────────────────────────────────
from app.config import get_settings
from app.database import Base

# ── Import ALL models so autogenerate can see them ───────────────────────────
import app.models  # noqa: F401 — side-effect import registers all ORM classes

# ── Alembic config object ─────────────────────────────────────────────────────
config = context.config

# Interpret the config file for Python logging
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# Set the SQLAlchemy URL from our settings (overrides alembic.ini if set)
settings = get_settings()
config.set_main_option("sqlalchemy.url", settings.effective_database_url)

target_metadata = Base.metadata


# ── Offline migrations (generate SQL without DB connection) ──────────────────

def run_migrations_offline() -> None:
    """
    Run migrations in 'offline' mode — generates SQL script without
    connecting to the database. Useful for reviewing changes.
    """
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,
        compare_server_default=True,
    )
    with context.begin_transaction():
        context.run_migrations()


# ── Online migrations (apply directly to DB) ─────────────────────────────────

def run_migrations_online() -> None:
    """
    Run migrations in 'online' mode — connects to the database and
    applies migrations directly.
    """
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,  # NullPool for migration scripts
    )
    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            compare_type=True,
            compare_server_default=True,
        )
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
