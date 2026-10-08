import gzip
import logging
import shutil
import sqlite3
import tempfile
from collections.abc import Callable
from datetime import datetime, timedelta, timezone
from pathlib import Path

from sqlalchemy.engine import make_url

from app.domains.backups.schemas import BackupResult
from app.domains.backups.storage import BackupStorage

logger = logging.getLogger(__name__)

BACKUP_FILE_PREFIX = "threecal-"
BACKUP_FILE_SUFFIX = ".db.gz"


class BackupError(Exception):
    pass


def sqlite_path_from_url(database_url: str) -> Path | None:
    """Return the on-disk SQLite file for a SQLAlchemy URL, or None for non-file databases."""
    url = make_url(database_url)
    if url.get_backend_name() != "sqlite":
        return None
    database = url.database
    if not database or database == ":memory:" or database.startswith("file::memory:"):
        return None
    return Path(database)


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class DatabaseBackupService:
    def __init__(
        self,
        *,
        storage: BackupStorage,
        database_url: str,
        prefix: str = "backups/",
        retention_days: int = 30,
        clock: Callable[[], datetime] = utc_now,
    ) -> None:
        self.storage = storage
        self.database_url = database_url
        self.prefix = prefix
        self.retention_days = retention_days
        self.clock = clock

    def run(self) -> BackupResult | None:
        """Snapshot, compress, upload and prune. Returns None when the database is not SQLite."""
        db_path = sqlite_path_from_url(self.database_url)
        if db_path is None:
            logger.info(
                "database backup skipped: only file-based SQLite databases are supported",
                extra={"database_backend": make_url(self.database_url).get_backend_name()},
            )
            return None
        if not db_path.is_file():
            raise BackupError(f"SQLite database file not found: {db_path}")

        now = self.clock()
        key = f"{self.prefix}{BACKUP_FILE_PREFIX}{now:%Y%m%dT%H%M%SZ}{BACKUP_FILE_SUFFIX}"

        with tempfile.TemporaryDirectory(prefix="threecal-backup-") as workdir:
            snapshot_path = Path(workdir) / "snapshot.db"
            archive_path = Path(workdir) / "snapshot.db.gz"
            self._snapshot(db_path, snapshot_path)
            with snapshot_path.open("rb") as source, gzip.open(archive_path, "wb") as target:
                shutil.copyfileobj(source, target)
            size_bytes = archive_path.stat().st_size
            self.storage.upload_file(key, archive_path, "application/gzip")

        logger.info("database backup uploaded", extra={"backup_key": key, "size_bytes": size_bytes})
        pruned = self.prune(now=now, keep={key})
        return BackupResult(key=key, size_bytes=size_bytes, pruned_keys=pruned)

    def prune(self, *, now: datetime, keep: set[str] | None = None) -> list[str]:
        if self.retention_days <= 0:
            return []
        cutoff = now - timedelta(days=self.retention_days)
        keep = keep or set()
        expired = [
            backup.key
            for backup in self.storage.list_backups(self.prefix)
            if backup.key not in keep
            and backup.key.removeprefix(self.prefix).startswith(BACKUP_FILE_PREFIX)
            and backup.key.endswith(BACKUP_FILE_SUFFIX)
            and backup.last_modified < cutoff
        ]
        if expired:
            self.storage.delete(expired)
            logger.info("old database backups deleted", extra={"deleted_count": len(expired)})
        return expired

    @staticmethod
    def _snapshot(source_path: Path, target_path: Path) -> None:
        # sqlite3's online backup API produces a consistent copy even while the app is writing.
        source = sqlite3.connect(f"{source_path.resolve().as_uri()}?mode=ro", uri=True)
        target = sqlite3.connect(target_path)
        try:
            with target:
                source.backup(target)
            result = target.execute("PRAGMA quick_check").fetchone()
            if not result or result[0] != "ok":
                raise BackupError(f"SQLite snapshot failed integrity check: {result}")
        finally:
            target.close()
            source.close()
