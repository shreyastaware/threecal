from datetime import datetime

from pydantic import BaseModel


class StoredBackup(BaseModel):
    key: str
    last_modified: datetime


class BackupResult(BaseModel):
    key: str
    size_bytes: int
    pruned_keys: list[str]
