"""SQLAlchemy declarative base.

Domain models are added in Phase 2.
"""

from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    pass
