## Context

See proposal.md for motivation. The application reads its configuration through
`core.config`, while Docker Compose consumes the same `.env` for service
variables. The two files must remain compatible and must not replace actual
provider credentials in the developer's `.env`.

## Goals / Non-Goals

**Goals:**

- Make the order of settings match operational ownership: PostgreSQL, Redis,
  alert delivery, Celery, scheduling, Flower, FastAPI/auth, then BP settings.
- Make `.env.example` runnable locally using clearly non-production defaults.
- Keep comments short, inline, and focused on what an operator needs to change.
- Add missing local Celery and Flower values to `.env` without disturbing
  existing secrets.

**Non-Goals:**

- Changing Pydantic setting names, their defaults in code, or Compose service
  topology.
- Rotating existing production/provider credentials.
- Introducing a secrets manager.

## Decisions

### Use service blocks and inline comments

Each block starts with a short heading such as `# --- PostgreSQL ---`; values
that need context use a short comment on the same line. Long introductory
paragraphs are removed. This makes the file scannable and preserves comments
next to the setting they describe.

Alternative considered: retain detailed paragraphs above each block. Rejected
because they obscure values and were the source of the reported confusion.

### Separate local defaults from real secrets

`.env.example` will contain safe development values such as
`POSTGRES_USER=postgres_user`, `FLOWER_BASIC_AUTH=admin:admin`, and a generated
non-empty development JWT key, each marked for replacement in production.
The real `.env` retains existing credentials; only missing Celery and Flower
settings are added. This avoids accidentally overwriting operational access.

Alternative considered: make `.env` identical to the example. Rejected because
the local file can contain private provider credentials.

### Keep alert delivery near Redis

Mail and Telegram delivery configuration, followed by `TRUE_ALERTING` and test
recipients, forms one compact alert-delivery block immediately after Redis.
`TRUE_ALERTING` comes first with a short description that it selects test or
real recipients; it does not enable or disable sending.

### Consolidate BP-1 settings

`TRUE_PARSING` is placed with all BP-1 variables. Adaptive-runner limits,
network settings, cache TTLs, runtime mode, and source circuit-breaker settings
are kept as compact BP-1 subsections with inline comments.

## Risks / Trade-offs

- [Example credentials copied to production] → Mark every example credential
  with a short inline production-replacement warning.
- [Accidental loss of local secret] → Preserve populated `.env` values and
  only move them during the mechanical reordering.
- [Compose variable omission] → Compare both files against `core.config` and
  run `docker compose config` after editing.
