# API v1

Wersja 1 publicznego kontraktu HTTP API. Wszystkie trasy montowane pod `/api/v1`.

## Pełna lista endpointów

### System

| Metoda | Ścieżka | Opis | Auth |
|---|---|---|---|
| GET | `/health` | Health check | Nie |
| GET | `/api/v1` | Status API | Nie |

### Auth

| Metoda | Ścieżka | Opis | Auth |
|---|---|---|---|
| POST | `/api/v1/auth/register` | Rejestracja | Nie |
| POST | `/api/v1/auth/login` | Logowanie → JWT | Nie |
| POST | `/api/v1/auth/refresh` | Odnowienie access token | Refresh token |
| POST | `/api/v1/auth/logout` | Wylogowanie | Bearer |
| GET | `/api/v1/auth/me` | Profil użytkownika | Bearer |
| PATCH | `/api/v1/auth/me` | Aktualizacja profilu | Bearer |

### Organizations

| Metoda | Ścieżka | Opis | Auth |
|---|---|---|---|
| POST | `/api/v1/organizations` | Utwórz org | Bearer |
| GET | `/api/v1/organizations` | Lista moich org | Bearer |
| GET | `/api/v1/organizations/{org_id}` | Szczegóły org | Bearer |
| PATCH | `/api/v1/organizations/{org_id}` | Aktualizuj org | Bearer (admin+) |
| DELETE | `/api/v1/organizations/{org_id}` | Usuń org | Bearer (owner) |
| POST | `/api/v1/organizations/{org_id}/members` | Zaproś membera | Bearer (admin+) |
| GET | `/api/v1/organizations/{org_id}/members` | Lista memberów | Bearer |
| DELETE | `/api/v1/organizations/{org_id}/members/{user_id}` | Usuń membera | Bearer (admin+) |

### Projects (router: `/repositories`)

| Metoda | Ścieżka | Opis | Auth |
|---|---|---|---|
| POST | `/api/v1/projects` | Utwórz projekt | Bearer |
| GET | `/api/v1/projects` | Lista projektów | Bearer |
| GET | `/api/v1/projects/{project_id}` | Szczegóły projektu | Bearer |
| PATCH | `/api/v1/projects/{project_id}` | Aktualizuj projekt | Bearer |
| DELETE | `/api/v1/projects/{project_id}` | Archiwizuj projekt | Bearer |

### Tasks + Time Tracking (router: `/pull-requests`)

| Metoda | Ścieżka | Opis | Auth |
|---|---|---|---|
| POST | `/api/v1/tasks` | Utwórz task | Bearer |
| GET | `/api/v1/tasks` | Lista tasków | Bearer |
| GET | `/api/v1/tasks/{task_id}` | Szczegóły taska | Bearer |
| PATCH | `/api/v1/tasks/{task_id}` | Aktualizuj task | Bearer |
| DELETE | `/api/v1/tasks/{task_id}` | Usuń task | Bearer |
| POST | `/api/v1/tasks/{task_id}/start` | Rozpocznij sesję pracy | Bearer |
| POST | `/api/v1/tasks/{task_id}/stop` | Zakończ sesję pracy | Bearer |
| GET | `/api/v1/tasks/{task_id}/sessions` | Historia sesji | Bearer |

### Metrics

| Metoda | Ścieżka | Opis | Auth |
|---|---|---|---|
| GET | `/api/v1/metrics/summary` | Podsumowanie produktywności | Bearer |
| GET | `/api/v1/metrics/velocity` | Velocity (taski/tydzień) | Bearer |
| GET | `/api/v1/metrics/time-tracking` | Czas pracy dziennie | Bearer |
| GET | `/api/v1/metrics/completion-rate` | % ukończonych tasków | Bearer |
| GET | `/api/v1/metrics/estimation-accuracy` | Dokładność estymacji | Bearer |
| GET | `/api/v1/metrics/streaks` | Streaki aktywności | Bearer |
| GET | `/api/v1/metrics/projects/{project_id}` | Metryki projektu | Bearer |

### Reports

| Metoda | Ścieżka | Opis | Auth |
|---|---|---|---|
| POST | `/api/v1/reports` | Wygeneruj raport | Bearer |
| GET | `/api/v1/reports` | Lista raportów | Bearer |
| GET | `/api/v1/reports/{report_id}` | Pobierz raport | Bearer |
| DELETE | `/api/v1/reports/{report_id}` | Usuń raport | Bearer |

### GitHub Integration

| Metoda | Ścieżka | Opis | Auth |
|---|---|---|---|
| POST | `/api/v1/integrations/github/authorize` | Inicjuj OAuth flow | Bearer |
| GET | `/api/v1/integrations/github/callback` | OAuth callback | — |
| GET | `/api/v1/integrations/github/status` | Status połączenia | Bearer |
| DELETE | `/api/v1/integrations/github/disconnect` | Odłącz GitHub | Bearer |
| POST | `/api/v1/integrations/github/sync` | Ręczna synchronizacja | Bearer |
| POST | `/api/v1/integrations/github/webhooks` | Webhook receiver | HMAC |

## Konwencje URL

- Zasoby w liczbie mnogiej: `/tasks`, `/projects`, `/organizations`
- ID zasobu w ścieżce: `/tasks/{task_id}` (UUID)
- Akcje jako pod-zasoby: `/tasks/{task_id}/start`, `/tasks/{task_id}/stop`
- Sub-kolekcje: `/organizations/{org_id}/members`
- Query params dla filtrowania: `?status=in_progress&priority=high`
- Paginacja: `?limit=20&offset=0` (domyślnie limit=20, max=100)

## Standardowe kody HTTP

| Kod | Kiedy |
|---|---|
| 200 | GET, PATCH — sukces |
| 201 | POST — zasób utworzony |
| 204 | DELETE — sukces, brak body |
| 400 | Błąd walidacji wejścia |
| 401 | Brak lub nieważny token |
| 403 | Brak uprawnień |
| 404 | Zasób nie istnieje |
| 409 | Konflikt (np. email zajęty) |
| 422 | Błąd parsowania requestu (Pydantic) |

## Format response z paginacją

```json
{
  "data": [...],
  "meta": {
    "total": 142,
    "limit": 20,
    "offset": 0
  }
}
```

## Status implementacji

| Router | Status |
|---|---|
| auth | Placeholder → do zaimplementowania |
| organizations | Placeholder → do zaimplementowania |
| repositories (projects) | Placeholder → do zaimplementowania |
| pull_requests (tasks) | Placeholder → do zaimplementowania |
| metrics | Placeholder → do zaimplementowania |
| reports | Placeholder → do zaimplementowania |
| integrations/github | Placeholder → do zaimplementowania |
