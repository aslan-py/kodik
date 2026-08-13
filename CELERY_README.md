# Pipeline Celery operations

The Compose stack starts the API, PostgreSQL, Redis, two workers, Beat, and
the optional Flower dashboard from the repository root.

```powershell
# Required once: set a local-only Flower account in .env.
# FLOWER_BASIC_AUTH=operator:use-a-long-unique-password
docker compose up -d --build
docker compose ps
```

`celery-worker` consumes `pipeline.control` and `pipeline.stages`.
`celery-worker-bp1` is intentionally separate and consumes only
`pipeline.bp1`; it contains the browser dependencies used by BP1. Beat is a
single process and polls the effective schedule at
`PIPELINE_SCHEDULE_POLL_SECONDS`.

## Operations

```powershell
# Apply schema changes without starting the entire stack.
docker compose run --rm migrate

# Follow an individual service.
docker compose logs -f celery-worker
docker compose logs -f celery-worker-bp1
docker compose logs -f celery-beat

# Inspect registered workers and queues.
docker compose exec api celery -A core.celery_app:app inspect ping
docker compose exec api celery -A core.celery_app:app inspect active_queues
```

Pipeline requests return a `run_id` immediately. Inspect the run through
`GET /pipeline/runs/{run_id}` or the **Pipeline runs** and **Pipeline stage
details** entries in FastAdmin. The Pipeline-runs list refreshes while it
contains queued or running rows. A queued/running run owns the single active
slot; a second launch receives HTTP 409 with that run id.

## Schedule and recovery

The base schedule lives in `.env` (`PIPELINE_SCHEDULE_ENABLED`,
`PIPELINE_SCHEDULE_CRON`, `PIPELINE_SCHEDULE_TIMEZONE`). Analysts can view or
temporarily override it through `/pipeline/schedule`; `{"reset": true}`
returns every field to the environment defaults. Beat records processed UTC
cron slots in PostgreSQL to prevent duplicates.

The watchdog marks an active run `stale` when its heartbeat exceeds
`PIPELINE_RUN_STALE_TIMEOUT_SECONDS`. The reconciler marks a committed run as
`failed` if its canvas publication was never confirmed. Neither mechanism
restarts terminal stage rows.

## Flower and production

Flower is bound to `127.0.0.1:${FLOWER_PORT:-5555}` and refuses to start if
`FLOWER_BASIC_AUTH` is empty. Do not expose it directly on a public interface.
For remote access, place it behind a TLS reverse proxy and keep basic-auth
credentials in the deployment secret store.

To roll back only this schema change, stop API/workers first, run
`alembic downgrade 44cc7e12d384` in the migrate container, then start the
stack again. Do not downgrade while a run owns the active slot.
