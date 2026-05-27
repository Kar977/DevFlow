# Metrics Routes

Endpointy do pobierania metryk produktywności developera.

Metryki obliczane są przez `MetricsService` na podstawie danych z tabel `tasks` i `work_sessions`.
Wymagają działającego modułu tasków z danymi.

## Endpointy do zaimplementowania

### `GET /api/v1/metrics/summary`

Pełne podsumowanie produktywności za wybrany okres.

Query params:
- `date_from` — ISO 8601 date (domyślnie: 30 dni temu)
- `date_to` — ISO 8601 date (domyślnie: dziś)

Response `200 OK`:
```json
{
  "velocity": {
    "value": 8.5,
    "previous_value": 6.0,
    "delta_percent": 41.7
  },
  "completion_rate": {
    "value": 72.3,
    "previous_value": 68.0,
    "delta_percent": 6.3
  },
  "active_hours_per_day": {
    "value": 5.2,
    "previous_value": 4.8,
    "delta_percent": 8.3
  },
  "current_streak": 7,
  "date_from": "2025-01-01",
  "date_to": "2025-01-31"
}
```

`previous_value` i `delta_percent` obliczane dla analogicznego okresu poprzedniego (np. jeśli `date_from/to` = ostatnie 30 dni, previous = 30 dni przed tym).

---

### `GET /api/v1/metrics/velocity`

Liczba ukończonych tasków per tydzień (ostatnie N tygodni).

Query params:
- `weeks` — liczba tygodni wstecz (domyślnie 8, max 52)

Response `200 OK`:
```json
{
  "current_week": 9,
  "trend": "up",
  "data": [
    { "week_start": "2025-01-06", "tasks_completed": 7 },
    { "week_start": "2025-01-13", "tasks_completed": 9 },
    { "week_start": "2025-01-20", "tasks_completed": 11 }
  ]
}
```

`trend`: `up` gdy ostatnie 3 tygodnie rosnące, `down` gdy malejące, `stable` inaczej.

---

### `GET /api/v1/metrics/time-tracking`

Dzienne godziny aktywnej pracy (suma `WorkSession.duration_minutes` per dzień).

Query params:
- `date_from`, `date_to`

Response `200 OK`:
```json
{
  "total_hours": 87.5,
  "data": [
    { "date": "2025-01-06", "minutes": 320 },
    { "date": "2025-01-07", "minutes": 195 }
  ]
}
```

Dni bez sesji nie są zwracane (sparse data).

---

### `GET /api/v1/metrics/completion-rate`

Procent tasków ukończonych w danym okresie.

Query params: `date_from`, `date_to`

Response `200 OK`:
```json
{
  "value": 72.3,
  "done_count": 47,
  "total_count": 65,
  "breakdown": {
    "done": 47,
    "cancelled": 5,
    "open": 13
  }
}
```

Formuła: `done / (done + cancelled + open) * 100`

---

### `GET /api/v1/metrics/estimation-accuracy`

Dokładność szacowania czasu tasków.

Query params: `date_from`, `date_to`

Response `200 OK`:
```json
{
  "ratio": 1.23,
  "category": "under_estimated",
  "tasks_analyzed": 18,
  "breakdown": {
    "accurate": 10,
    "under_estimated": 6,
    "over_estimated": 2
  }
}
```

Kategorie:
- `accurate`: ratio 0.8–1.2 (real time mieści się w ±20% estymacji)
- `under_estimated`: ratio > 1.2 (zajęło więcej niż zakładano)
- `over_estimated`: ratio < 0.8 (zajęło mniej niż zakładano)

Liczone tylko dla tasków z `status=done` i uzupełnionym `estimate_minutes`.

---

### `GET /api/v1/metrics/streaks`

Streaki aktywności — serie dni z zamkniętym przynajmniej 1 taskiem.

Response `200 OK`:
```json
{
  "current_streak": 7,
  "longest_streak": 15,
  "streak_start": "2025-01-20"
}
```

---

### `GET /api/v1/metrics/projects/{project_id}`

Metryki dla konkretnego projektu.

Query params: `date_from`, `date_to`

Response `200 OK`:
```json
{
  "project_id": "uuid",
  "total_tasks": 42,
  "open_tasks": 15,
  "overdue_tasks": 3,
  "completion_rate": 64.2,
  "health_status": "at_risk",
  "velocity": { ... },
  "time_spent_hours": 156.5
}
```

`health_status`: `healthy` (<10% overdue), `at_risk` (10–30%), `critical` (>30%).

---

## Cachowanie

Zapytania do metryk są kosztowne — agregacje na wielu wierszach. Należy cachować wyniki.

**Klucz cache:** `metrics:{user_id}:{endpoint}:{date_from}:{date_to}`

**TTL:** 5 minut (krótki bo user może właśnie zamknąć task i chcieć zobaczyć efekt)

Implementacja:
- Etap 1: słownik in-memory w `MetricsService` z `datetime` expiry
- Etap 2: Redis (gdy Redis zostanie dodany do infrastruktury)

Cache należy invalidować przy:
- Zamknięciu taska (`status` → `done`)
- Zakończeniu sesji pracy (`WorkSession.stop`)

---

## Pliki do stworzenia

- `routes.py` — route handlery (zastąpić obecny placeholder)
- `../../../core/schemas/metrics/` — schematy response (opis w `core/schemas/README.md`)
- `../../../core/services/metrics.py` — `MetricsService`
- Brak nowych modeli/repozytoriów — `MetricsService` korzysta z `TaskRepository` i `WorkSessionRepository`
