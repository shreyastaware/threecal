# Threecal API

FastAPI + SQLAlchemy + Alembic, managed with [uv](https://docs.astral.sh/uv/).

```bash
uv sync
uv run alembic upgrade head
uv run uvicorn app.main:app --reload
uv run pytest -q
uv run ruff check app tests alembic && uv run mypy app
```

Provider credentials are encrypted with `CREDENTIALS_ENCRYPTION_KEY`. Keep this key stable and secret; changing it makes existing provider credentials unreadable.

## Deploying to Railway

The API is built from `backend/Dockerfile`. The container runs `alembic upgrade head` and then uvicorn on `$PORT`, as an unprivileged `app` user (the entrypoint only uses root to `chown` the volume, which Railway mounts as root).

1. **Create the service** from this repo. In *Settings*: root directory `/backend`, config file path `/backend/railway.toml` (Dockerfile builder, `/health` healthcheck, restart on failure, no deploy overlap).
2. **Attach a volume** mounted at `/data`.
3. **Set variables** (see `.env.example` for the full list):
   - `ENVIRONMENT=production`, `AUTO_CREATE_TABLES=false` (schema comes from Alembic only)
   - `DATABASE_URL=sqlite:////data/threecal.db` (four slashes = absolute path on the volume)
   - `JWT_SECRET_KEY`, `CREDENTIALS_ENCRYPTION_KEY`, `WEBHOOK_SECRET`: long random values
   - `AUTH_COOKIE_SECURE=true`, `CORS_ORIGINS=https://threecal.com`, `FRONTEND_URL`, `PUBLIC_API_URL`
   - `EMAIL_PROVIDER=smtp` + `SMTP_*` (Brevo SMTP credentials)
   - `R2_*` credentials, optionally `BACKUP_R2_BUCKET_NAME` (a **private** bucket for backups)
   - `SCHEDULER_ENABLED=true`
   - Observability: `SENTRY_DSN`, `SENTRY_TRACES_SAMPLE_RATE` (e.g. `0.1`), `LOKI_URL`, `LOKI_USERNAME`, `LOKI_PASSWORD`, `LOG_LEVEL`
4. Keep the service at **one replica**: Railway volumes do not support replicas, and SQLite needs a single writer.

### Scheduled jobs

A Railway volume can only be attached to one service, so separate Railway cron services cannot open the SQLite file. With `SCHEDULER_ENABLED=true`, the API process runs the jobs itself (`app/jobs/scheduler.py`), each in a worker thread:

| Job | Schedule | Manual run |
| --- | --- | --- |
| Expire unpaid pending bookings | every `EXPIRE_PENDING_BOOKINGS_INTERVAL_MINUTES` (default 5) | `python -m app.jobs.expire_pending_bookings` |
| SQLite backup to R2 | daily at `BACKUP_HOUR_UTC` (default 03:00 UTC) | `python -m app.jobs.backup_database` |

An appointment reminders job will be added to the same scheduler later. Manual runs (for example over `railway ssh`) exit non-zero on failure. Once the database moves to PostgreSQL, the jobs can move to Railway cron services (start command `python -m app.jobs.<job>`) and the scheduler can be switched off.

### Database backups

`python -m app.jobs.backup_database` takes a consistent snapshot with SQLite's online backup API, runs `PRAGMA quick_check`, gzips it and uploads it to `backups/threecal-YYYYMMDDTHHMMSSZ.db.gz` in `BACKUP_R2_BUCKET_NAME` (falls back to `R2_BUCKET_NAME`). Backups older than `BACKUP_RETENTION_DAYS` (default 30) are deleted. Non-SQLite databases are skipped.

Restore: download the object, `gunzip` it, stop the service, replace `/data/threecal.db` and start the service again.

### Observability

- **Logs**: JSON lines on stdout (`timestamp`, `level`, `logger`, `message`, `request_id`, extras), one access line per request (`method`, `path`, `status`, `duration_ms`; `/health` skipped). Every response carries `X-Request-ID` (an incoming one is reused). With `LOKI_URL` set, logs are also pushed to Grafana Loki in background batches with labels `app`, `environment`, `level`. For Grafana Cloud, take the URL, user id and an access token with `logs:write` from *Connections → Loki*.
- **Errors**: Sentry is enabled when `SENTRY_DSN` is set. The environment defaults to `ENVIRONMENT`, the release to `RAILWAY_GIT_COMMIT_SHA`, and PII is not sent.
