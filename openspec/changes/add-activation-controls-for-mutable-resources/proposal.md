## Why

Soft deletion is the project convention for configurable registries, but several `PATCH` request schemas exclude `is_active`. As a result, an analyst or administrator must use `DELETE` to deactivate a record and cannot reactivate it or change its state through the documented partial-update operation. User administration is also limited to role changes despite needing to manage a user's department and activity.

## What Changes

- Make `is_active` an explicitly supported optional field of every `PATCH` operation for a mutable resource that exposes soft `DELETE`.
- Extend administrative user updates so an `analyst` or `admin` can independently update a target user's `role`, `department_id`, and `is_active` without enabling self-service privilege escalation.
- Extend `GET /filter-options` with the `showcase.media` reference list and make every returned media value applicable through `GET /showcase?media=...`.
- Replace the enumerated `action_items.deadline` values in `GET /filter-options` with inclusive `from`/`to` bounds, and replace exact action-item deadline filtering with inclusive `deadline_from`/`deadline_to` query parameters.
- Preserve the current `DELETE` endpoints as the backward-compatible shortcut for setting `is_active=false`.
- Add contract tests that verify deactivation and reactivation via `PATCH`, preservation of unspecified fields, authorization, and the new user-administration fields.

## Capabilities

### New Capabilities

- None.

### Modified Capabilities

- `api/http-endpoint-contract`: Define consistent `PATCH` activation control for soft-deletable resources and full administrative updates of a user's role, department, and active state.

## Impact

- Affected API endpoints: `/users/{user_id}/role`, and the existing item `PATCH` endpoints for competitors, sources, triggers, search tasks, black domains, stop words, topic limits, categories, departments, event types, channels, and routing rules.
- Affected read endpoints: `/filter-options`, `/showcase`, and `/action-items`.
- Affected code: Pydantic update schemas, the user endpoint/service contract, OpenAPI descriptions/responses as needed, and API endpoint tests.
- No database migration, external dependency, or removal of current `DELETE` behavior is required.
