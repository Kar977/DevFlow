# Auth Routes

User authentication and session management.

## Endpoints to Implement

### `POST /api/v1/auth/register`

Register a new user.

Request:
```json
{
  "email": "dev@example.com",
  "password": "minimum8chars",
  "full_name": "Jane Smith"
}
```

Response `201 Created`:
```json
{
  "id": "uuid",
  "email": "dev@example.com",
  "full_name": "Jane Smith",
  "avatar_url": null,
  "created_at": "2025-01-01T10:00:00Z"
}
```

Errors: `409 Conflict` when email is already taken.

---

### `POST /api/v1/auth/login`

Log in — returns a JWT token pair.

Request:
```json
{
  "email": "dev@example.com",
  "password": "minimum8chars"
}
```

Response `200 OK`:
```json
{
  "access_token": "eyJ...",
  "refresh_token": "opaque-random-token",
  "token_type": "bearer",
  "expires_in": 900
}
```

`expires_in` = 900 seconds (15 minutes) for the access token.
Errors: `401 Unauthorized` for invalid credentials (same message for both cases — do not reveal whether the email exists).

---

### `POST /api/v1/auth/refresh`

Renew the access token using a refresh token.

Request:
```json
{
  "refresh_token": "opaque-random-token"
}
```

Response `200 OK`:
```json
{
  "access_token": "eyJ...",
  "token_type": "bearer",
  "expires_in": 900
}
```

Errors: `401` when the token is expired or revoked.

---

### `POST /api/v1/auth/logout`

Revokes the refresh token. Requires header: `Authorization: Bearer <access_token>`.

Response `204 No Content`.

---

### `GET /api/v1/auth/me`

Profile of the currently authenticated user. Requires `Authorization: Bearer`.

Response `200 OK`:
```json
{
  "id": "uuid",
  "email": "dev@example.com",
  "full_name": "Jane Smith",
  "avatar_url": null,
  "created_at": "2025-01-01T10:00:00Z"
}
```

---

### `PATCH /api/v1/auth/me`

Update profile. All fields are optional (PATCH semantics).

Request:
```json
{
  "full_name": "New Name",
  "avatar_url": "https://example.com/avatar.png"
}
```

Response `200 OK`: updated `UserResponse`.

---

## Implementation Status

Implemented — see `routes.py`, `../../../core/schemas/auth/`,
`../../../core/services/auth.py` (`AuthService`),
`../../../core/repositories/user.py` (`UserRepository`),
`../../../core/repositories/refresh_token.py` (`RefreshTokenRepository`),
`../../../core/models/user.py`, `../../../core/models/refresh_token.py`,
and Alembic migration `0001_create_users_and_refresh_tokens.py`.

JWT is signed/verified with `PyJWT`, passwords hashed with `bcrypt` (both in
`../../../core/security.py`) — not `python-jose`/`passlib` as originally
sketched here.

## `core/security.py`

`get_current_subject()` is a real dependency (not a `501` placeholder): it
decodes and verifies the bearer JWT via `decode_access_token()` and returns
an `AuthenticatedSubject`. See `../../../core/security.py`.
