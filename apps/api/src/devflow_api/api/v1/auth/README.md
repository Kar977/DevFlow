# Auth Routes

Autentykacja i zarządzanie sesją użytkownika.

## Endpointy do zaimplementowania

### `POST /api/v1/auth/register`

Rejestracja nowego użytkownika.

Request:
```json
{
  "email": "dev@example.com",
  "password": "minimum8chars",
  "full_name": "Jan Kowalski"
}
```

Response `201 Created`:
```json
{
  "id": "uuid",
  "email": "dev@example.com",
  "full_name": "Jan Kowalski",
  "avatar_url": null,
  "created_at": "2025-01-01T10:00:00Z"
}
```

Błędy: `409 Conflict` gdy email już zajęty.

---

### `POST /api/v1/auth/login`

Logowanie — zwraca parę tokenów JWT.

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

`expires_in` = 900 sekund (15 minut) dla access token.
Błędy: `401 Unauthorized` gdy dane nieprawidłowe (jeden komunikat dla obu przypadków — nie ujawniaj czy email istnieje).

---

### `POST /api/v1/auth/refresh`

Odnowienie access token przy użyciu refresh token.

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

Błędy: `401` gdy token wygasł lub unieważniony.

---

### `POST /api/v1/auth/logout`

Unieważnia refresh token. Wymagany header: `Authorization: Bearer <access_token>`.

Response `204 No Content`.

---

### `GET /api/v1/auth/me`

Profil zalogowanego użytkownika. Wymagany `Authorization: Bearer`.

Response `200 OK`:
```json
{
  "id": "uuid",
  "email": "dev@example.com",
  "full_name": "Jan Kowalski",
  "avatar_url": null,
  "created_at": "2025-01-01T10:00:00Z"
}
```

---

### `PATCH /api/v1/auth/me`

Aktualizacja profilu. Wszystkie pola opcjonalne (PATCH semantics).

Request:
```json
{
  "full_name": "Nowe Imię",
  "avatar_url": "https://example.com/avatar.png"
}
```

Response `200 OK`: zaktualizowany `UserResponse`.

---

## Pliki do stworzenia

- `routes.py` — route handlery (zastąpić obecny placeholder)
- `../../../core/schemas/auth/` — schematy (opis w `core/schemas/README.md`)
- `../../../core/services/auth.py` — `AuthService`
- `../../../core/repositories/user.py` — `UserRepository`
- `../../../core/repositories/refresh_token.py` — `RefreshTokenRepository`
- `../../../core/models/user.py` — model `User`
- `../../../core/models/refresh_token.py` — model `RefreshToken`
- Migracja Alembic: tabele `users` i `refresh_tokens`

## Zależności do dodania (`pyproject.toml`)

```toml
python-jose = {extras = ["cryptography"], version = ">=3.3"}
passlib = {extras = ["bcrypt"], version = ">=1.7"}
```

## Wypełnienie `core/security.py`

Funkcja `get_current_subject()` aktualnie zwraca `501`. Należy ją zastąpić:

```python
async def get_current_subject(
    credentials: HTTPAuthorizationCredentials = Depends(HTTPBearer()),
    session: AsyncSession = Depends(get_session),
) -> AuthenticatedSubject:
    # Dekoduj JWT (python-jose)
    # Zweryfikuj podpis, expiry
    # Zwróć AuthenticatedSubject(subject_id=UUID(payload["sub"]))
```
