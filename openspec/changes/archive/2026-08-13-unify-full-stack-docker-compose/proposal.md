## Why

The repository currently has duplicated and misplaced frontend deployment files, and its root Compose file neither builds the frontend from its real directory nor starts the API it references. A fresh developer cannot start the complete application with one documented Docker command.

## What Changes

- Establish one root `docker-compose.yml` that starts the frontend, FastAPI backend, PostgreSQL, Redis, and database migrations as a coherent local stack.
- Add a production-oriented backend Dockerfile so Python dependencies and runtime prerequisites are installed inside the image rather than on each developer machine.
- Keep all Next.js source, assets, manifests, and frontend Docker configuration in `frontend/`; remove duplicate frontend-only files from the repository root.
- Restore the historical npm manifest and lock file to `frontend/` and correct ignore rules so they remain versioned.
- Configure browser-to-backend traffic through the frontend's `/api` proxy, avoiding Docker-internal hostnames in browser configuration.
- Keep the Compose layout extensible for the `move-pipeline-to-celery` change, which will subsequently add Celery workers, Beat, and Flower.

## Capabilities

### New Capabilities

- `deployment/full-stack-compose`: a reproducible single-command Docker Compose environment for the frontend, API, database, Redis, and schema migration.

### Modified Capabilities

- None.

## Impact

Affected areas include root Docker/Compose configuration, `frontend/` build configuration and npm manifests, `.gitignore`, `.env.example`, backend runtime startup, and operational documentation. The public API contract is unchanged.
