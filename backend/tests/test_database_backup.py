import gzip
import sqlite3
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from app.domains.backups.schemas import StoredBackup
from app.domains.backups.service import BackupError, DatabaseBackupService, sqlite_path_from_url

NOW = datetime(2026, 10, 8, 3, 0, 0, tzinfo=timezone.utc)


class FakeBackupStorage:
    def __init__(self, existing: list[StoredBackup] | None = None) -> None:
        self.objects: dict[str, bytes] = {}
        self.listing: list[StoredBackup] = list(existing or [])
        self.deleted: list[str] = []

    def upload_file(self, key: str, path: Path, content_type: str) -> None:
        assert content_type == "application/gzip"
        self.objects[key] = path.read_bytes()
        self.listing.append(StoredBackup(key=key, last_modified=NOW))

    def list_backups(self, prefix: str) -> list[StoredBackup]:
        return [backup for backup in self.listing if backup.key.startswith(prefix)]

    def delete(self, keys: list[str]) -> None:
        self.deleted.extend(keys)


def _make_database(path: Path) -> None:
    with sqlite3.connect(path) as connection:
        connection.execute("CREATE TABLE bookings (id INTEGER PRIMARY KEY, name TEXT)")
        connection.execute("INSERT INTO bookings (name) VALUES ('first'), ('second')")
    connection.close()


def _service(storage: FakeBackupStorage, database_url: str, retention_days: int = 30) -> DatabaseBackupService:
    return DatabaseBackupService(
        storage=storage,
        database_url=database_url,
        prefix="backups/",
        retention_days=retention_days,
        clock=lambda: NOW,
    )


def test_backup_uploads_gzipped_consistent_snapshot(tmp_path: Path) -> None:
    db_path = tmp_path / "threecal.db"
    _make_database(db_path)
    storage = FakeBackupStorage()

    result = _service(storage, f"sqlite:///{db_path}").run()

    assert result is not None
    assert result.key == "backups/threecal-20261008T030000Z.db.gz"
    restored = tmp_path / "restored.db"
    restored.write_bytes(gzip.decompress(storage.objects[result.key]))
    with sqlite3.connect(restored) as connection:
        rows = connection.execute("SELECT name FROM bookings ORDER BY id").fetchall()
    connection.close()
    assert rows == [("first",), ("second",)]
    assert result.size_bytes == len(storage.objects[result.key])


def test_backup_prunes_only_expired_backup_files(tmp_path: Path) -> None:
    db_path = tmp_path / "threecal.db"
    _make_database(db_path)
    old = NOW - timedelta(days=31)
    recent = NOW - timedelta(days=5)
    storage = FakeBackupStorage(
        existing=[
            StoredBackup(key="backups/threecal-20260901T030000Z.db.gz", last_modified=old),
            StoredBackup(key="backups/threecal-20261003T030000Z.db.gz", last_modified=recent),
            StoredBackup(key="backups/manual-export.sql", last_modified=old),
        ]
    )

    result = _service(storage, f"sqlite:///{db_path}").run()

    assert result is not None
    assert result.pruned_keys == ["backups/threecal-20260901T030000Z.db.gz"]
    assert storage.deleted == ["backups/threecal-20260901T030000Z.db.gz"]


def test_backup_skips_non_sqlite_databases() -> None:
    storage = FakeBackupStorage()

    result = _service(storage, "postgresql://user:pass@localhost/threecal").run()

    assert result is None
    assert storage.objects == {}


def test_backup_fails_when_database_file_is_missing(tmp_path: Path) -> None:
    with pytest.raises(BackupError):
        _service(FakeBackupStorage(), f"sqlite:///{tmp_path / 'missing.db'}").run()


@pytest.mark.parametrize(
    ("url", "expected"),
    [
        ("sqlite:///./threecal.db", Path("./threecal.db")),
        ("sqlite:////data/threecal.db", Path("/data/threecal.db")),
        ("sqlite://", None),
        ("sqlite:///:memory:", None),
        ("postgresql+psycopg://localhost/threecal", None),
    ],
)
def test_sqlite_path_from_url(url: str, expected: Path | None) -> None:
    assert sqlite_path_from_url(url) == expected


def test_backup_job_exits_non_zero_on_failure(monkeypatch: pytest.MonkeyPatch) -> None:
    from app.jobs import runner

    def failing_job() -> None:
        raise RuntimeError("boom")

    monkeypatch.setattr(runner, "configure_logging", lambda: None)
    monkeypatch.setattr(runner, "init_sentry", lambda: False)
    with pytest.raises(SystemExit) as exc_info:
        runner.run_job("failing", failing_job)
    assert exc_info.value.code == 1


def test_daily_schedule_targets_next_configured_hour() -> None:
    from app.jobs.scheduler import daily_at

    delay = daily_at(3)
    assert delay(datetime(2026, 10, 8, 1, 30, tzinfo=timezone.utc)) == timedelta(hours=1, minutes=30)
    assert delay(datetime(2026, 10, 8, 3, 0, tzinfo=timezone.utc)) == timedelta(days=1)
