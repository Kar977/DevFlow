# Projects Routes

Router `repositories` obsługuje domenę **projektów developerskich**.

Projekt to kontener dla tasków. Może być osobisty (bez `org_id`) lub należący do organizacji.
Opcjonalnie powiązany z repozytorium GitHub przez `github_repo_url`.

## Endpointy do zaimplementowania

### `POST /api/v1/projects`

Utwórz nowy projekt.

Request:
```json
{
  "name": "DevFlow Backend",
  "description": "API dla DevFlow Insight",
  "org_id": "uuid-lub-null",
  "github_repo_url": "https://github.com/owner/repo"
}
```

Response `201 Created`:
```json
{
  "id": "uuid",
  "name": "DevFlow Backend",
  "description": "API dla DevFlow Insight",
  "status": "active",
  "org_id": null,
  "github_repo_url": "https://github.com/owner/repo",
  "created_at": "2025-01-01T10:00:00Z"
}
```

Jeśli `org_id` podane: serwis weryfikuje że user jest memberem tej org.

---

### `GET /api/v1/projects`

Lista projektów użytkownika (osobistych + z org do których należy).

Query params:
- `org_id` — filtruj po organizacji
- `status` — `active` | `archived` (domyślnie: `active`)
- `limit` — (domyślnie 20, max 100)
- `offset`

Response `200 OK`:
```json
{
  "data": [ { ...ProjectResponse } ],
  "meta": { "total": 5, "limit": 20, "offset": 0 }
}
```

---

### `GET /api/v1/projects/{project_id}`

Szczegóły projektu wraz ze statystykami tasków.

Response `200 OK`:
```json
{
  "id": "uuid",
  "name": "DevFlow Backend",
  "status": "active",
  "stats": {
    "total_tasks": 42,
    "open_tasks": 15,
    "overdue_tasks": 3,
    "completion_rate": 64.2
  },
  ...
}
```

---

### `PATCH /api/v1/projects/{project_id}`

Aktualizacja projektu. Wszystkie pola opcjonalne.

Request: `UpdateProjectRequest`.
Response `200 OK`: zaktualizowany `ProjectResponse`.

---

### `DELETE /api/v1/projects/{project_id}`

Archiwizacja projektu (zmiana `status` na `archived`, nie usunięcie z bazy).
Taski projektu pozostają nienaruszone.

Response `204 No Content`.

---

## Pliki do stworzenia

- `routes.py` — route handlery (zastąpić obecny placeholder)
- `../../../core/schemas/projects/` — `CreateProjectRequest`, `UpdateProjectRequest`, `ProjectResponse`, `ProjectStatsResponse`
- `../../../core/services/project.py` — `ProjectService`
- `../../../core/repositories/project.py` — `ProjectRepository`
- `../../../core/models/project.py` — model `Project`
- Migracja Alembic: tabela `projects`

## Uwaga — nazewnictwo URL

Endpoint URL to `/api/v1/projects`, ale router w kodzie (`api/v1/repositories/`) zachowuje oryginalną nazwę katalogu dla ciągłości scaffoldu. Prefix routera należy zmienić w `routes.py`:

```python
router = APIRouter(prefix="/projects", tags=["Projects"])
```
