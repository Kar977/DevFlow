# Organizations Routes

Workspace and team management. An organization is a container for projects and members.

## Endpoints to Implement

### `POST /api/v1/organizations`

Create a new organization. The creator is automatically assigned the `owner` role.

Request:
```json
{
  "name": "My Team",
  "description": "Organization description"
}
```

Response `201 Created`:
```json
{
  "id": "uuid",
  "name": "My Team",
  "slug": "my-team",
  "description": "Organization description",
  "created_at": "2025-01-01T10:00:00Z"
}
```

`slug` is generated automatically from `name` (lowercase, hyphens, unique).

---

### `GET /api/v1/organizations`

List organizations the authenticated user belongs to.

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

Organization details. Accessible only to members.

Response `200 OK`: `OrganizationResponse`.
Errors: `404` when it does not exist or the user is not a member.

---

### `PATCH /api/v1/organizations/{org_id}`

Update name/description. Requires `admin` or `owner` role.

Request: `UpdateOrganizationRequest` (optional fields).
Response `200 OK`: updated `OrganizationResponse`.

---

### `DELETE /api/v1/organizations/{org_id}`

Soft delete (sets `deleted_at`). Requires `owner` role.

Response `204 No Content`.
Error: `403` when the user is not the owner.

---

### `POST /api/v1/organizations/{org_id}/members`

Invite a user to the organization by email. Requires `admin` or `owner` role.

Request:
```json
{
  "email": "colleague@example.com",
  "role": "member"
}
```

Response `201 Created`: `MemberResponse`.
Errors: `404` when the email does not exist in the system, `409` when the user is already a member.

---

### `GET /api/v1/organizations/{org_id}/members`

List organization members.

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

Remove a member from the organization. Requires `admin` or `owner` role.

Response `204 No Content`.
Error: `400` when attempting to remove the sole owner.

---

## Files to Create

- `routes.py` — route handlers
- `../../../core/schemas/organizations/` — schemas
- `../../../core/services/organization.py` — `OrganizationService`
- `../../../core/repositories/organization.py` — `OrganizationRepository`
- `../../../core/models/organization.py` — `Organization` + `OrganizationMember` models
- Alembic migration: `organizations` and `organization_members` tables

## Authorization

Role permissions matrix:

| Action | member | admin | owner |
|---|---|---|---|
| Read org and members | ✅ | ✅ | ✅ |
| Edit org | ❌ | ✅ | ✅ |
| Invite/remove member | ❌ | ✅ | ✅ |
| Delete org | ❌ | ❌ | ✅ |
| Change role to owner | ❌ | ❌ | ✅ |
