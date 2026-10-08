from datetime import datetime, timezone
from functools import lru_cache
from pathlib import Path
from typing import Protocol

import boto3
from botocore.client import BaseClient
from botocore.config import Config
from botocore.exceptions import BotoCoreError, ClientError

from app.core.config import settings
from app.domains.backups.schemas import StoredBackup


class BackupStorageError(Exception):
    pass


class BackupStorage(Protocol):
    """Destination for database snapshots. Swap implementations to target S3, GCS, local disk, etc."""

    def upload_file(self, key: str, path: Path, content_type: str) -> None: ...

    def list_backups(self, prefix: str) -> list[StoredBackup]: ...

    def delete(self, keys: list[str]) -> None: ...


class R2BackupStorage:
    def __init__(
        self,
        *,
        account_id: str,
        access_key_id: str,
        secret_access_key: str,
        bucket_name: str,
    ) -> None:
        self.account_id = account_id
        self.access_key_id = access_key_id
        self.secret_access_key = secret_access_key
        self.bucket_name = bucket_name
        self._s3_client: BaseClient | None = None

    def upload_file(self, key: str, path: Path, content_type: str) -> None:
        try:
            self._client().upload_file(
                str(path),
                self.bucket_name,
                key,
                ExtraArgs={"ContentType": content_type},
            )
        except (BotoCoreError, ClientError) as exc:
            raise BackupStorageError("Cloudflare R2 rejected the backup upload.") from exc

    def list_backups(self, prefix: str) -> list[StoredBackup]:
        backups: list[StoredBackup] = []
        try:
            paginator = self._client().get_paginator("list_objects_v2")
            for page in paginator.paginate(Bucket=self.bucket_name, Prefix=prefix):
                for item in page.get("Contents", []):
                    last_modified: datetime = item["LastModified"]
                    if last_modified.tzinfo is None:
                        last_modified = last_modified.replace(tzinfo=timezone.utc)
                    backups.append(StoredBackup(key=item["Key"], last_modified=last_modified))
        except (BotoCoreError, ClientError) as exc:
            raise BackupStorageError("Could not list backups in Cloudflare R2.") from exc
        return backups

    def delete(self, keys: list[str]) -> None:
        try:
            # DeleteObjects accepts at most 1000 keys per request.
            for start in range(0, len(keys), 1000):
                chunk = keys[start : start + 1000]
                self._client().delete_objects(
                    Bucket=self.bucket_name,
                    Delete={"Objects": [{"Key": key} for key in chunk], "Quiet": True},
                )
        except (BotoCoreError, ClientError) as exc:
            raise BackupStorageError("Cloudflare R2 rejected the backup delete request.") from exc

    def _client(self) -> BaseClient:
        if self._s3_client is not None:
            return self._s3_client

        missing = [
            name
            for name, value in {
                "R2_ACCOUNT_ID": self.account_id,
                "R2_ACCESS_KEY_ID": self.access_key_id,
                "R2_SECRET_ACCESS_KEY": self.secret_access_key,
                "BACKUP_R2_BUCKET_NAME or R2_BUCKET_NAME": self.bucket_name,
            }.items()
            if not value
        ]
        if missing:
            raise BackupStorageError(f"Missing Cloudflare R2 backup settings: {', '.join(missing)}")

        self._s3_client = boto3.client(
            "s3",
            endpoint_url=f"https://{self.account_id}.r2.cloudflarestorage.com",
            aws_access_key_id=self.access_key_id,
            aws_secret_access_key=self.secret_access_key,
            region_name="auto",
            config=Config(signature_version="s3v4"),
        )
        return self._s3_client


@lru_cache
def get_backup_storage() -> BackupStorage:
    return R2BackupStorage(
        account_id=settings.r2_account_id,
        access_key_id=settings.r2_access_key_id,
        secret_access_key=settings.r2_secret_access_key,
        bucket_name=settings.backup_r2_bucket_name or settings.r2_bucket_name,
    )
