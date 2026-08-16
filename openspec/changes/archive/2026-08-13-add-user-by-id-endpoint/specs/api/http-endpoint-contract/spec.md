## ADDED Requirements

### Requirement: Authorized user retrieval by identifier
The API SHALL provide `GET /users/{user_id}` for an authenticated `analyst` or `admin`. For an existing identifier, it SHALL return `200` and the existing `UserRead` response representation. For a valid identifier that does not identify a user, it SHALL return the documented `404` response.

#### Scenario: Authorized caller retrieves an existing user
- **WHEN** an authenticated analyst or administrator requests `GET /users/{user_id}` for an existing user
- **THEN** the API returns `200` and that user's `UserRead` representation

#### Scenario: Requested user does not exist
- **WHEN** an authenticated analyst or administrator requests `GET /users/{user_id}` for an identifier that is not present
- **THEN** the API returns the documented `404` response

#### Scenario: Caller lacks user administration access
- **WHEN** an unauthenticated caller or an authenticated role other than analyst or admin requests `GET /users/{user_id}`
- **THEN** the API returns the role-policy response and does not disclose the requested user's data
