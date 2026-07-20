"""Compatibility exports for the original scaffold.

Schemas now live with their owning business domains.
"""

from app.domains.auth.schemas import RegisterRequest as UserCreate
from app.domains.users.schemas import UserRead

__all__ = ["UserCreate", "UserRead"]
