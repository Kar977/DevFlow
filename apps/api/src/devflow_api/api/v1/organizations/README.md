# Organizations Routes

Zarządzanie workspace'ami i zespołami (organizations). Organization jest kontenerem dla projektów i memberów.

## Endpointy do zaimplementowania

### `POST /api/v1/organizations`

Utwórz nową organizację. Creator automatycznie dostaje rolę `owner`.

Request:
```json
{
  "name": "My Team",
  "description": "Opis organizacji"
}
```

Response `201 Created`:
```json
{
  "id": "uuid",
  "name": "My Team",
  "slug": "my-team",
  "description": "Opis organizacji",
  "created_at": "2025-01-01T10:00:00Z"
}
```

`slug` generowany automatycznie z `name` (lowercase, myślniki, unique).

---

### `GET /api/v1/organizations`

Lista organizacji do których należy zalogowany użytkownik.

Response `200 OK`:
```json
{
  "data": [
    { "id": "uuid", "name": "My Team", "slug": "my-team", ... }
  ],
  "meta": { "total": 2, "limit": 20, "offset": 0 }
}
```

---

### `GET /api/v1/organizations/{org_id}`

Szczegóły organizacji. Dostępne tylko dla memberów.

Response `200 OK`: `OrganizationResponse`.
Błędy: `404` gdy nie istnieje lub user nie jest memberem.

---

### `PATCH /api/v1/organizations/{org_id}`

Aktualizacja nazwy/opisu. Wymaga roli `admin` lub `owner`.

Request: `UpdateOrganizationRequest` (pola opcjonalne).
Response `200 OK`: zaktualizowany `OrganizationResponse`.

---

### `DELETE /api/v1/organizations/{org_id}`

Soft delete (ustawia `deleted_at`). Wymaga roli `owner`.

Response `204 No Content`.
Błąd: `403` gdy user nie jest ownerem.

---

### `POST /api/v1/organizations/{org_id}/members`

Zaproś użytkownika do organizacji po emailu. Wymaga roli `admin` lub `owner`.

Request:
```json
{
  "email": "colleague@example.com",
  "role": "member"
}
```

Response `201 Created`: `MemberResponse`.
Błąd: `404` gdy email nie istnieje w systemie, `409` gdy user już jest memberem.

---

### `GET /api/v1/organizations/{org_id}/members`

Lista memberów organizacji.

Response `200 OK`:
```json
{
  "data": [
    {
      "user_id": "uuid",
      "role": "owner",
      "joined_at": "2025-01-01T10:00:00Z",
      "user": { "id": "uuid", "email": "...", "full_name": "..." }
    }
  ]
}
```

---

### `DELETE /api/v1/organizations/{org_id}/members/{user_id}`

Usuń membera z organizacji. Wymaga `admin` lub `owner`.

Response `204 No Content`.
Błąd: `400` gdy próba usunięcia jedynego ownera.

---

## Pliki do stworzenia

- `routes.py` — route handlery
- `../../../core/schemas/organizations/` — schematy
- `../../../core/services/organization.py` — `OrganizationService`
- `../../../core/repositories/organization.py` — `OrganizationRepository`
- `../../../core/models/organization.py` — modele `Organization` + `OrganizationMember`
- Migracja Alembic: tabele `organizations` i `organization_members`

## Autoryzacja

Role i ich uprawnienia:

| Akcja | member | admin | owner |
|---|---|---|---|
| Czytaj org i memberów | ✅ | ✅ | ✅ |
| Edytuj org | ❌ | ✅ | ✅ |
| Zaproś/usuń membera | ❌ | ✅ | ✅ |
| Usuń org | ❌ | ❌ | ✅ |
| Zmień rolę na owner | ❌ | ❌ | ✅ |
