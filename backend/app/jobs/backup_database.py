from typing import Any

from app.core.config import settings
from app.domains.backups.service import DatabaseBackupService
from app.domains.backups.storage import get_backup_storage
from app.jobs.runner import run_job


def backup_database() -> dict[str, Any] | None:
    service = DatabaseBackupService(
        storage=get_backup_storage(),
        database_url=settings.database_url,
        prefix=settings.backup_prefix,
        retention_days=settings.backup_retention_days,
    )
    result = service.run()
    return result.model_dump() if result else None


def main() -> None:
    run_job("backup_database", backup_database)


if __name__ == "__main__":
    main()
