# Reports Routes

Generowanie i pobieranie raportów produktywności.

Raporty generowane asynchronicznie jako background tasks. Po zleceniu user dostaje `report_id`
i może odpytywać o status dopóki `status` nie zmieni się na `ready`.

## Endpointy do zaimplementowania

### `POST /api/v1/reports`

Zlecenie wygenerowania raportu.

Request:
```json
{
  "type": "weekly_summary",
  "format": "json",
  "date_from": "2025-01-20",
  "date_to": "2025-01-26"
}
```

Typy raportów:
- `weekly_summary` — podsumowanie tygodnia: velocity, czas pracy, ukończone taski
- `project_status` — status projektu (wymaga `project_id` w request)
- `productivity_overview` — szerszy przegląd produktywności za wybrany okres

Formaty:
- `json` — zwracany jako `payload` w response
- `csv` — link do pobrania w `file_url`

Response `202 Accepted`:
```json
{
  "id": "uuid",
  "type": "weekly_summary",
  "format": "json",
  "status": "pending",
  "payload": null,
  "file_url": null,
  "generated_at": null,
  "created_at": "2025-01-27T10:00:00Z"
}
```

Generowanie uruchamiane przez `FastAPI BackgroundTasks` — nie blokuje odpowiedzi.

---

### `GET /api/v1/reports`

Lista raportów zalogowanego użytkownika.

Query params: `limit`, `offset`

Response `200 OK`:
```json
{
  "data": [
    {
      "id": "uuid",
      "type": "weekly_summary",
      "format": "json",
      "status": "ready",
      "generated_at": "2025-01-27T10:01:05Z",
      "created_at": "2025-01-27T10:00:00Z"
    }
  ],
  "meta": { "total": 12, "limit": 20, "offset": 0 }
}
```

---

### `GET /api/v1/reports/{report_id}`

Pobranie raportu. Jeśli `status=ready`, `payload` lub `file_url` są wypełnione.

Response `200 OK`:
```json
{
  "id": "uuid",
  "type": "weekly_summary",
  "format": "json",
  "status": "ready",
  "payload": {
    "period": { "from": "2025-01-20", "to": "2025-01-26" },
    "tasks_completed": 9,
    "total_work_hours": 32.5,
    "velocity": 9,
    "top_projects": [ ... ]
  },
  "file_url": null,
  "generated_at": "2025-01-27T10:01:05Z"
}
```

Gdy `status=pending` lub `generating`: payload jest null, client powinien odpytywać ponownie.
Gdy `status=failed`: payload null, `error_message` wyjaśnia błąd.

---

### `DELETE /api/v1/reports/{report_id}`

Usuń raport.

Response `204 No Content`.
Błąd: `403` gdy raport należy do innego usera.

---

## Cykl życia raportu

```
POST /reports → status: "pending"
    ↓ (background task starts)
status: "generating"
    ↓ (success)
status: "ready" + payload/file_url wypełnione
    ↓ (or failure)
status: "failed" + error_message
```

---

## Struktura payload dla `weekly_summary`

```json
{
  "period": {
    "from": "2025-01-20",
    "to": "2025-01-26"
  },
  "tasks_completed": 9,
  "tasks_created": 12,
  "total_work_hours": 32.5,
  "work_days": 5,
  "avg_hours_per_day": 6.5,
  "velocity": 9,
  "completion_rate": 75.0,
  "top_projects": [
    { "name": "DevFlow Backend", "tasks_completed": 6 }
  ],
  "tasks": [
    {
      "id": "uuid",
      "title": "Implement auth",
      "status": "done",
      "project": "DevFlow Backend",
      "work_minutes": 210
    }
  ]
}
```

---

## Pliki do stworzenia

- `routes.py` — route handlery (zastąpić obecny placeholder)
- `../../../core/schemas/reports/` — `CreateReportRequest`, `ReportResponse`
- `../../../core/services/report.py` — `ReportService` + background task generator
- `../../../core/repositories/report.py` — `ReportRepository`
- `../../../core/models/report.py` — model `Report`
- Migracja Alembic: tabela `reports`
