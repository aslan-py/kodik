## Why

Administrative frontend flows need to retrieve one known user directly by identifier instead of requesting and filtering the full users collection.

## What Changes

- Add `GET /users/{user_id}` returning one user in the existing user response shape.
- Apply the same analyst/admin access policy used for the existing users collection.
- Return the documented not-found response when the identifier does not exist.
- Add endpoint and service tests covering successful, missing, unauthenticated, and unauthorized requests.

## Capabilities

### New Capabilities

- None.

### Modified Capabilities

- `api/http-endpoint-contract`: the users API gains an authorized read-by-identifier operation and its defined responses.

## Impact

Affected areas are the users endpoint and service, response definitions, API tests, and generated OpenAPI documentation. No database schema change is required.
