## Context

See `proposal.md` and the API delta specification for the requested behaviour. The reference-resource routers already route `PATCH` payloads through a shared partial-update service, and `DELETE` already implements a soft state change. The missing capability is at the request-schema boundary: many update schemas do not expose `is_active`. User administration is separate from the reference factory and currently passes only a role value to its service.

## Goals / Non-Goals

**Goals:**

- Make activation state a first-class optional field in every mutable soft-delete resource's update schema.
- Reuse the present partial-update and soft-delete semantics, including existing authorization and integrity-error mapping.
- Let administrative user updates change any supplied combination of role, department, and activity state while retaining the safety boundary around `/users/me`.
- Provide a data-derived `media` reference for the showcase and make it directly usable as a showcase filter.
- Replace deadline enumeration with range bounds, so clients can render and submit a date interval without receiving every distinct date.

**Non-Goals:**

- Do not remove or repurpose `DELETE`, change persistence models, add hard deletion, or modify static/read-only resources.
- Do not broaden write access beyond `analyst` and `admin`, or allow users to alter their own role/activity through `/users/me`.
- Do not add user profile fields or alter pipeline handling of inactive records.

## Decisions

### Expose `is_active` through existing partial-update schemas

Add `is_active: bool | None = None` to each update schema for the twelve resources with soft `DELETE`: competitor, source, trigger, search task, black domain, stop word, topic limit, category, department, event type, channel, and routing rule. The routers already serialize with `exclude_unset=True`, so an omitted flag does not mutate a record while an explicit `false` or `true` does.

This is preferred over dedicated `/activate` and `/deactivate` actions because it matches the API's existing partial-update model, allows reactivation, and avoids duplicating routes, permissions, service logic, and API documentation. The existing `DELETE` remains a compatible convenience alias for deactivation.

### Evolve the existing user-administration request contract in place

Extend the payload model consumed by `PATCH /users/{user_id}/role` with optional `role`, `department_id`, and `is_active` fields, and rename its internal intent/documentation from role-only update to administrative user update where appropriate. Its service method will build changes with `exclude_unset=True`, validate a supplied department identifier using the existing user data-access helper, apply only supplied fields, commit once, and return `UserRead`.

Keeping the endpoint path avoids an unnecessary breaking API change. A separate `/users/{id}` `PATCH` was considered but rejected because it would create two competing administrative update contracts and require client migration. The self-service schema stays `extra='forbid'` and continues to omit `role` and `is_active`.

### Verify the common contract parametrically and the user contract directly

Add parameterized endpoint tests covering every soft-delete resource for `PATCH is_active=false` followed by `PATCH is_active=true`, including an assertion that a separately stored field remains unchanged. Add focused user tests for each supported administrative field, combined partial updates, an invalid department, authorization, and rejected self-service privilege/activity fields.

Parameterized tests prevent individual resource schemas from drifting; direct user tests cover its distinct validation and authorization path.

### Add the media reference and filter as one contract

Add `media` to the `showcase` section of `GET /filter-options`. Its values are unique, non-empty values of `showcase_event.media`, sorted case-insensitively like the other data-derived showcase references. Add an optional `media` parameter to `GET /showcase`; it performs the same case-insensitive substring matching used for the human-readable `region` and `competitor` fields.

The reference and query parameter must be delivered together: a frontend must be able to pass a returned value back to the showcase endpoint and find the matching visible rows. `media` remains a fact field and is not made editable through the showcase PATCH endpoint.

### Return action-item deadline bounds instead of enumerating dates

Replace `action_items.deadline: list[date]` with `action_items.deadline: {from: date | null, to: date | null}`. The values are respectively the minimum and maximum non-null deadline among action items visible to the caller; when no visible deadline exists, both are `null`. Viewer scoping remains identical to all other action-item options.

Replace the exact `deadline` query parameter of `GET /action-items` with optional inclusive `deadline_from` and `deadline_to` parameters. Each may be used independently; when both are supplied, the API returns deadlines within the closed interval. Reject an inverted interval (`deadline_from > deadline_to`) with `422`. This is an intentional contract replacement: clients must not rely on an array of individual dates or the retired exact-date parameter.

## Risks / Trade-offs

- [A patch schema is missed while a DELETE route exists] → Derive the test parameter list from the complete audited set of soft-delete endpoints and compare it with registered API routes.
- [A request sends an empty administrative user payload] → Preserve current partial-update semantics (return the unchanged representation) and document the result in the endpoint description.
- [A department is deactivated or missing] → Retain existing foreign-key/existence validation; the requested change only requires reassignment to an existing department and does not change department lifecycle policy.
- [A client still sends the retired `deadline` parameter] → Treat the filter change as a documented API-contract change, update generated OpenAPI and frontend consumers together, and reject unknown parameters according to the endpoint's existing validation policy.
- [Existing clients rely on `DELETE`] → Keep its exact soft-deactivation behaviour and response shape.

## Migration Plan

1. Deploy the API/schema and test changes together; no data migration is required because all targeted models already persist `is_active`.
2. Existing clients may continue using `DELETE`; clients that need reactivation or combined updates can begin using `PATCH` immediately.
3. If rollback is required, revert the API release. Previously changed `is_active` values remain valid persisted state and can be corrected through the retained `DELETE` or the prior administration tooling.
