"""Compatibility exports for the original scaffold.

New code should import database primitives from ``app.core.database``.
"""

from app.core.database import Base, SessionLocal, engine, get_db

__all__ = ["Base", "SessionLocal", "engine", "get_db"]
