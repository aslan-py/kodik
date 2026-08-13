## 1. Users read endpoint

- [x] 1.1 Add `GET /users/{user_id}` using the existing analyst/admin authorization policy and `UserRead` response shape.
- [x] 1.2 Add service-layer lookup and documented `404` handling for a missing user.
- [x] 1.3 Add endpoint response metadata so the operation is correctly represented in OpenAPI.

## 2. Verification

- [x] 2.1 Add tests for successful retrieval, a missing user, no authentication, and insufficient role.
- [x] 2.2 Run focused users API tests and strict OpenSpec validation.
