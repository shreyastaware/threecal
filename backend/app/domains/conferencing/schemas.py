import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict


class AuthorizationUrlRead(BaseModel):
    authorization_url: str


class ConferencingConnectionRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    provider: str
    account_email: str
    status: str
    created_at: datetime
