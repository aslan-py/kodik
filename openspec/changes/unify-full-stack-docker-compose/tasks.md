## 1. Frontend ownership and reproducibility

- [x] 1.1 Restore the historical `package.json` and `package-lock.json` into `frontend/` and correct Git ignore rules so npm manifests are versioned.
- [x] 1.2 Move or remove duplicate root frontend-only files so the frontend's assets and Next.js configuration are owned by `frontend/`.
- [x] 1.3 Configure the frontend to use same-origin `/api` requests and proxy them to the API service within Docker Compose.

## 2. Backend image and unified orchestration

- [x] 2.1 Add a backend Dockerfile and Docker ignore rules that build the FastAPI runtime from the repository root.
- [x] 2.2 Replace the root Compose definition with one full-stack configuration for PostgreSQL, Redis, migrations, API, and frontend, including health-gated dependencies and container-specific host settings.
- [x] 2.3 Remove the duplicate frontend Compose entry point and update local run documentation to name the root Compose command as canonical.

## 3. Verification

- [x] 3.1 Validate the Compose model with `docker compose config` using safe example configuration.
- [x] 3.2 Build and start the full stack, verify service health, migrations, frontend availability, API availability, and frontend `/api` proxy routing.
- [x] 3.3 Run focused backend and frontend checks appropriate to the changed configuration, then record the exact outcomes.
