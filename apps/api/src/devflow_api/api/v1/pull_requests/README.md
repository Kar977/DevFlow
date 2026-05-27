# Tasks Routes

Router `pull_requests` obsługuje domenę **tasków i śledzenia czasu pracy**.

Task to podstawowy element pracy: może być tworzony ręcznie lub importowany z GitHub (PR/Issue).
Do każdego taska można przypiąć sesję pracy z timerem.

## Endpointy do zaimplementowania

### `POST /api/v1/tasks`

Utwórz nowy task.

Request:
```json
{
  "title": "Implement auth module",
  "description": "JWT-based auth with refresh tokens",
  "project_id": "uuid-lub-null",
  "priority": "high",
  "estimate_minutes": 240,
  "assignee_id": "uuid-lub-null",
  "due_date": "2025-02-01"
}
```

Response `201 Created`:
```json
{
  "id": "uuid",
  "title": "Implement auth module",
  "status": "backlog",
  "priority": "high",
  "estimate_minutes": 240,
  "assignee_id": null,
  "project_id": "uuid",
  "due_date": "2025-02-01",
  "source": "manual",
  "github_url": null,
  "created_at": "2025-01-01T10:00:00Z",
  "updated_at": "2025-01-01T10:00:00Z"
}
```

---

### `GET /api/v1/tasks`

Lista tasków z filtrowaniem i paginacją.

Query params:
- `project_id` — filtruj po projekcie
- `status` — `backlog` | `todo` | `in_progress` | `review` | `done` | `cancelled`
- `priority` — `low` | `medium` | `high` | `critical`
- `assignee_id` — filtruj po assignee
- `limit` (domyślnie 20, max 100)
- `offset`

Response `200 OK`:
```json
{
  "data": [ { ...TaskResponse } ],
  "meta": { "total": 37, "limit": 20, "offset": 0 }
}
```

---

### `GET /api/v1/tasks/{task_id}`

Szczegóły taska.

Response `200 OK`: `TaskResponse`.
Błąd: `404` gdy nie istnieje lub user nie ma dostępu.

---

### `PATCH /api/v1/tasks/{task_id}`

Aktualizacja taska. Tylko pola które user chce zmienić (PATCH semantics).

Request: `UpdateTaskRequest` (wszystkie pola opcjonalne).
Response `200 OK`: zaktualizowany `TaskResponse`.

Przykład zmiany statusu:
```json
{ "status": "in_progress" }
```

---

### `DELETE /api/v1/tasks/{task_id}`

Usuń task (hard delete). Usuwa też powiązane `WorkSession`.

Response `204 No Content`.

---

### `POST /api/v1/tasks/{task_id}/start`

Rozpocznij sesję pracy na tasku (uruchom timer).

- Jeśli user ma już aktywną sesję na **innym** tasku: błąd `409` z informacją który task jest aktywny.
- Jeśli task ma status `backlog` lub `todo`: automatycznie zmień na `in_progress`.

Response `201 Created`:
```json
{
  "id": "uuid",
  "task_id": "uuid",
  "started_at": "2025-01-01T10:00:00Z",
  "ended_at": null,
  "duration_minutes": null
}
```

---

### `POST /api/v1/tasks/{task_id}/stop`

Zakończ aktywną sesję pracy (zatrzymaj timer).

- `duration_minutes` obliczane automatycznie: `(ended_at - started_at).seconds // 60`
- Minimum 1 minuta (sesje poniżej 1 min zapisywane jako 1 min)

Response `200 OK`:
```json
{
  "id": "uuid",
  "task_id": "uuid",
  "started_at": "2025-01-01T10:00:00Z",
  "ended_at": "2025-01-01T12:30:00Z",
  "duration_minutes": 150
}
```

Błąd: `404` gdy nie ma aktywnej sesji dla tego taska i usera.

---

### `GET /api/v1/tasks/{task_id}/sessions`

Historia sesji pracy na tasku.

Response `200 OK`:
```json
{
  "data": [
    {
      "id": "uuid",
      "started_at": "2025-01-01T10:00:00Z",
      "ended_at": "2025-01-01T12:30:00Z",
      "duration_minutes": 150
    }
  ],
  "total_minutes": 310
}
```

---

## Statusy taska — przejścia

```
backlog → todo → in_progress → review → done
                      ↓                   ↓
                  cancelled           cancelled
```

Serwis nie egzekwuje ściśle przejść — user może ustawiać dowolny status (np. bezpośrednio backlog → done).
`source: 'github_pr'` i `source: 'github_issue'` taski mają status synchronizowany z GitHubem.

---

## Pliki do stworzenia

- `routes.py` — route handlery (zastąpić obecny placeholder)
- `../../../core/schemas/tasks/` — `CreateTaskRequest`, `UpdateTaskRequest`, `TaskResponse`, `WorkSessionResponse`
- `../../../core/services/task.py` — `TaskService`
- `../../../core/repositories/task.py` — `TaskRepository`
- `../../../core/repositories/work_session.py` — `WorkSessionRepository`
- `../../../core/models/task.py` — model `Task`
- `../../../core/models/work_session.py` — model `WorkSession`
- Migracja Alembic: tabele `tasks` i `work_sessions`

## Uwaga — nazewnictwo URL

Prefix routera należy zmienić w `routes.py`:

```python
router = APIRouter(prefix="/tasks", tags=["Tasks"])
```
