"""Database connection, engine configuration, and session management."""

from __future__ import annotations

import logging
import os
from contextlib import contextmanager
from pathlib import Path
from typing import Generator, Optional
from dotenv import load_dotenv
from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, declarative_base, sessionmaker
from sqlalchemy.pool import NullPool

load_dotenv()

logger = logging.getLogger(__name__)

Base = declarative_base()

_engine: Optional[Engine] = None
_SessionFactory: Optional[sessionmaker] = None


def get_database_url() -> str:
    """
    Retrieve DATABASE_URL from environment.
    Converts postgres:// or postgresql:// to postgresql+psycopg:// if needed.
    """
    url = os.getenv("DATABASE_URL", "").strip()
    if not url:
        return ""
    if url.startswith("postgres://"):
        url = url.replace("postgres://", "postgresql+psycopg://", 1)
    elif url.startswith("postgresql://") and not url.startswith("postgresql+"):
        url = url.replace("postgresql://", "postgresql+psycopg://", 1)
    return url


def get_engine(database_url: Optional[str] = None) -> Engine:
    """
    Get or create SQLAlchemy Engine.
    Uses NullPool for Supabase transaction pooler to prevent idle connection exhaustion.
    """
    global _engine, _SessionFactory
    target_url = database_url or get_database_url()

    if not target_url:
        raise ValueError(
            "DATABASE_URL is not set. Please configure DATABASE_URL in .env or provide a connection string."
        )

    if _engine is None or (database_url and _engine.url.render_as_string(hide_password=False) != target_url):
        is_sqlite = target_url.startswith("sqlite")
        connect_args = {}
        if not is_sqlite:
            # Needed for Supabase transaction poolers (PgBouncer)
            connect_args = {
                "prepare_threshold": None  # disable server-side prepared statements in psycopg3
            }

        _engine = create_engine(
            target_url,
            poolclass=NullPool if not is_sqlite else None,
            connect_args=connect_args if not is_sqlite else {},
            echo=False,
            future=True,
        )
        _SessionFactory = sessionmaker(bind=_engine, autoflush=False, autocommit=False)

    return _engine


@contextmanager
def get_db_session(engine: Optional[Engine] = None) -> Generator[Session, None, None]:
    """Context manager for acquiring and safely releasing a database session."""
    global _SessionFactory
    eng = engine or get_engine()
    if _SessionFactory is None or _SessionFactory.kw.get("bind") != eng:
        _SessionFactory = sessionmaker(bind=eng, autoflush=False, autocommit=False)

    session: Session = _SessionFactory()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def run_schema_migration(engine: Optional[Engine] = None, schema_file: Optional[Path | str] = None) -> None:
    """Execute database/schema.sql against the connected PostgreSQL database."""
    eng = engine or get_engine()
    file_path = Path(schema_file) if schema_file else Path(__file__).resolve().parent.parent / "database" / "schema.sql"

    if not file_path.is_file():
        raise FileNotFoundError(f"Schema file not found: {file_path}")

    sql_statements = file_path.read_text(encoding="utf-8")

    with eng.connect() as conn:
        with conn.begin():
            # Split and execute individual statements
            for stmt in sql_statements.split(";"):
                clean = stmt.strip()
                if clean:
                    conn.execute(text(clean))
        logger.info("Database schema applied successfully.")
