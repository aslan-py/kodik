## Purpose

Provide a reproducible local environment in which the entire Kodik web application can be started from the repository root without locally installing its runtime dependencies.

## ADDED Requirements

### Requirement: One-command full-stack startup
The repository SHALL provide one root Docker Compose configuration that starts the web frontend, API, PostgreSQL, Redis, and required database schema migration from a repository checkout.

#### Scenario: Fresh developer starts the application
- **WHEN** a developer with Docker and a configured root `.env` runs `docker compose up --build` from the repository root
- **THEN** the frontend, API, PostgreSQL, and Redis become available without a local Python virtual environment or local Node dependency installation

#### Scenario: API starts after its prerequisites
- **WHEN** Docker Compose starts the application stack
- **THEN** the API starts only after PostgreSQL is healthy and the schema migration has completed successfully

### Requirement: Frontend remains self-contained
The frontend SHALL be built from `frontend/`, and its source, static assets, Node manifests, and frontend-specific build configuration MUST reside within that directory.

#### Scenario: Frontend image build
- **WHEN** Compose builds the frontend image
- **THEN** its build context is `frontend/` and it uses the manifests and Dockerfile stored there

#### Scenario: Repository root is inspected
- **WHEN** a developer inspects frontend-specific artifacts in the repository root
- **THEN** duplicate Next.js source configuration and frontend static assets are absent

### Requirement: Browser API routing works in containers
The frontend SHALL expose browser API requests through a same-origin `/api` route and forward them to the API service inside the Compose network.

#### Scenario: Browser calls an API endpoint
- **WHEN** a browser served by the frontend requests `/api/auth/login`
- **THEN** the request is forwarded to the API service without exposing an internal Docker hostname to the browser

### Requirement: Frontend dependency manifests are versioned
The frontend npm manifest and lock file MUST be versioned in Git and MUST NOT contain runtime secrets.

#### Scenario: Clean frontend image build
- **WHEN** the frontend image is built from a clean checkout
- **THEN** its dependency installation uses the committed manifest and lock file
