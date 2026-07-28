from functools import lru_cache
from typing import Protocol
from urllib.parse import quote, unquote, urlparse

import boto3
from botocore.client import BaseClient
from botocore.config import Config
from botocore.exceptions import BotoCoreError, ClientError

from app.core.config import settings


class ObjectStorageError(Exception):
    pass


class ObjectStorageConfigurationError(ObjectStorageError):
    pass


class ObjectStorage(Protocol):
    def upload(self, key: str, content: bytes, content_type: str) -> str:
        pass

    def delete(self, key: str) -> None:
        pass

    def key_from_public_url(self, public_url: str) -> str | None:
        pass


class R2ObjectStorage:
    def __init__(
        self,
        *,
        account_id: str,
        access_key_id: str,
        secret_access_key: str,
        bucket_name: str,
        public_base_url: str,
    ) -> None:
        self.account_id = account_id
        self.access_key_id = access_key_id
        self.secret_access_key = secret_access_key
        self.bucket_name = bucket_name
        self.public_base_url = public_base_url.rstrip("/")
        self._s3_client: BaseClient | None = None

    def upload(self, key: str, content: bytes, content_type: str) -> str:
        try:
            self._client().put_object(
                Bucket=self.bucket_name,
                Key=key,
                Body=content,
                ContentType=content_type,
                CacheControl="public, max-age=31536000, immutable",
            )
        except (BotoCoreError, ClientError) as exc:
            raise ObjectStorageError("Cloudflare R2 rejected the upload.") from exc
        return f"{self.public_base_url}/{quote(key, safe='/')}"

    def delete(self, key: str) -> None:
        try:
            self._client().delete_object(Bucket=self.bucket_name, Key=key)
        except (BotoCoreError, ClientError) as exc:
            raise ObjectStorageError("Cloudflare R2 rejected the delete request.") from exc

    def key_from_public_url(self, public_url: str) -> str | None:
        if not self.public_base_url:
            return None

        base = urlparse(self.public_base_url)
        candidate = urlparse(public_url)
        base_path = base.path.rstrip("/")
        if (
            candidate.scheme != base.scheme
            or candidate.netloc != base.netloc
            or not candidate.path.startswith(f"{base_path}/")
        ):
            return None
        return unquote(candidate.path[len(base_path) + 1 :])

    def _client(self) -> BaseClient:
        if self._s3_client is not None:
            return self._s3_client

        missing = [
            name
            for name, value in {
                "R2_ACCOUNT_ID": self.account_id,
                "R2_ACCESS_KEY_ID": self.access_key_id,
                "R2_SECRET_ACCESS_KEY": self.secret_access_key,
                "R2_BUCKET_NAME": self.bucket_name,
                "R2_PUBLIC_BASE_URL": self.public_base_url,
            }.items()
            if not value
        ]
        if missing:
            raise ObjectStorageConfigurationError(
                f"Missing Cloudflare R2 settings: {', '.join(missing)}"
            )

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
def get_object_storage() -> ObjectStorage:
    return R2ObjectStorage(
        account_id=settings.r2_account_id,
        access_key_id=settings.r2_access_key_id,
        secret_access_key=settings.r2_secret_access_key,
        bucket_name=settings.r2_bucket_name,
        public_base_url=settings.r2_public_base_url,
    )
