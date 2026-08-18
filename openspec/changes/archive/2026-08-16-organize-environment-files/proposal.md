## Why

Current `.env` and `.env.example` mix unrelated settings, leave required
example values blank, and explain many values in long blocks above the
configuration. This makes local setup and handoff error-prone.

## What Changes

- Reorder both environment files into concise service-oriented blocks.
- Provide safe, usable local example values for infrastructure, Celery, Flower,
  API, JWT, and pipeline settings.
- Move alert delivery settings next to Redis and simplify their comments.
- Group all BP-1 settings together and replace long explanatory blocks with
  short inline comments where they help.
- Add the required Celery and Flower settings to the local `.env`; Flower will
  use the requested local account `admin:admin`.
- Preserve real third-party credentials in `.env`; placeholders and explicit
  change-before-production guidance belong in `.env.example`.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

None. This is configuration hygiene and does not change application behavior.

## Impact

- `.env` and `.env.example`
- Local Docker Compose startup and developer onboarding
- No API, database schema, or runtime feature contract changes
