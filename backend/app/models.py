"""Compatibility exports for the original scaffold.

Models now live with their owning business domains.
"""

from app.domains.auth.models import OAuthAccount
from app.domains.users.models import User

__all__ = ["OAuthAccount", "User"]
