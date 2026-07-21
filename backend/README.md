## Volume billing operations

Apply database migrations before deployment:

```bash
alembic upgrade head
```

Configure Railway Cron to run the monthly billing reconciler daily. The job only processes billing cycles that have ended and is idempotent:

```bash
python -m app.jobs.run_billing_cycle
```

Provider credentials are encrypted with `CREDENTIALS_ENCRYPTION_KEY`. Keep this key stable and secret; changing it makes existing provider credentials unreadable.
