"""
Database initialisation — creates tables and seeds data.
Called from FastAPI's lifespan handler on startup.
"""
from __future__ import annotations

from sqlalchemy.orm import Session

from db.database import Base, SessionLocal, engine
from db.seed import run_seed

# Import all models so SQLAlchemy registers them before create_all
import db.models  # noqa: F401


def init_db() -> None:
    """Create all tables (if they don't exist) and seed initial data."""
    Base.metadata.create_all(bind=engine)
    db: Session = SessionLocal()
    try:
        run_seed(db)
    finally:
        db.close()
