## Context

The root Compose file currently builds a Next.js image from the repository root, does not declare the API service it references, and duplicates a second frontend-oriented Compose file under `frontend/`. The project has a Python API whose settings are derived from root `.env`; the active `move-pipeline-to-celery` change will later extend the same stack with worker processes.

## Goals / Non-Goals

**Goals:**

- Make the base web stack reproducible with Docker alone.
- Establish the root Compose file as the only service orchestrator.
- Make `frontend/` the only home for frontend sources and its build inputs.
- Keep service naming, networks, health checks, and environment overrides ready for Celery services to join later.

**Non-Goals:**

- Adding Celery workers, Beat, Flower, or pipeline orchestration; those remain owned by `move-pipeline-to-celery`.
- Rewriting frontend application code or changing the public API.
- Publishing images to a remote registry or implementing CI/CD.

## Decisions

### One Compose file at the repository root

The root Compose file will own all service definitions. `frontend/docker-compose.yml` will be removed to eliminate conflicting entry points. This makes `docker compose up --build` the canonical command. Splitting into independently runnable frontend and backend Compose files was rejected because it reintroduces network, environment, and startup-order drift.

### Separate production images per runtime

`frontend/Dockerfile` will continue to build the Node/Next.js runtime using `frontend/` as context. A new root backend Dockerfile will install Python requirements and copy backend application code. Sharing one image between Node and Python was rejected because it bloats the image and couples unrelated toolchains.

### Explicit migration service and health-gated startup

Compose will run Alembic as a one-shot `migrate` service after PostgreSQL becomes healthy. API depends on migration completion; frontend depends on API availability. This avoids relying on developer-run migrations and avoids making API startup mutate schema. Running migrations in every API command was rejected because concurrent API replicas could race.

### Container-specific settings supplied by Compose

The root `.env` remains the source for credentials and published ports. Compose overrides service host names with Docker DNS names (`postgres`, `redis`) and binds the API to all interfaces. This preserves host-native development defaults while making container traffic reliable.

### Same-origin API proxy

The frontend will use `NEXT_PUBLIC_API_URL=/api`; a Next.js rewrite proxies that path to `api:8000` from inside the Docker network. This prevents browser code from seeing Docker service names and removes CORS as a requirement for normal containerized frontend traffic. Direct API access stays available through the API's published port for Swagger and diagnostics.

### Versioned npm manifests

The known historical `package.json` and `package-lock.json` will be restored under `frontend/`; ignore rules will stop excluding them. The lock file is required for deterministic `npm ci`. Secrets remain confined to ignored `.env*` files.

## Risks / Trade-offs

- [The historical lock file may not reflect newer frontend imports] → build the image and run the frontend build; update dependencies only when the resulting error identifies an actual missing package.
- [Frontend proxy configuration is evaluated in a Next.js runtime/build phase] → validate with an in-container request after Compose startup.
- [Existing root `.env` uses localhost hosts] → compose service overrides use Docker DNS names while leaving host-native runs unchanged.
- [Database migration can fail due to an existing inconsistent volume] → document `docker compose down -v` as a local-only reset, without executing it automatically.

## Migration Plan

1. Restore the frontend npm manifests from the existing Git history and relocate the remaining frontend-only root files.
2. Replace duplicated Compose configuration with the root full-stack definition and add the backend image.
3. Build and start the stack, then validate service health and frontend-to-API routing.
4. Roll back by restoring the previous Compose and Docker files from Git; named database volumes are not removed by that rollback.
