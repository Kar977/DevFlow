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

## Files to Create

- `routes.py` — route handlers (replace current placeholder)
- `../../../core/schemas/auth/` — schemas (described in `core/schemas/README.md`)
- `../../../core/services/auth.py` — `AuthService`
- `../../../core/repositories/user.py` — `UserRepository`
- `../../../core/repositories/refresh_token.py` — `RefreshTokenRepository`
- `../../../core/models/user.py` — `User` model
- `../../../core/models/refresh_token.py` — `RefreshToken` model
- Alembic migration: `users` and `refresh_tokens` tables

## Dependencies to Add (`pyproject.toml`)

```toml
python-jose = {extras = ["cryptography"], version = ">=3.3"}
passlib = {extras = ["bcrypt"], version = ">=1.7"}
```

## Filling in `core/security.py`

The `get_current_subject()` function currently returns `501`. Replace it with:

```python
async def get_current_subject(
    credentials: HTTPAuthorizationCredentials = Depends(HTTPBearer()),
    session: AsyncSession = Depends(get_session),
) -> AuthenticatedSubject:
    # Decode JWT (python-jose)
    # Verify signature and expiry
    # Return AuthenticatedSubject(subject_id=UUID(payload["sub"]))
```
