# DevFlow API

FastAPI backend dla DevFlow Insight — platforma produktywności i task management dla developerów.

## Development

Instalacja i uruchomienie z katalogu `apps/api/`:

```powershell
uv sync
uv run ruff format --check .
uv run ruff check .
uv run mypy src tests
uv run pytest
```

Uruchomienie serwera deweloperskiego:

```powershell
uv run uvicorn devflow_api.main:app --reload
```

## Architektura

Architektura warstwowa z egzekwowanymi granicami:

```
HTTP Request
    │
    ▼
Routes (api/v1/)          ← validacja wejścia, delegacja do serwisu
    │
    ▼
Services (core/services/) ← logika biznesowa, orchestracja
    │
    ▼
Repositories (core/repositories/) ← dostęp do danych
    │
    ▼
Models (core/models/)     ← SQLAlchemy ORM, stan w bazie
    │
    ▼
PostgreSQL
```

**Zasada:** Routes nie importują Repositories bezpośrednio. Serwisy nie znają FastAPI.

## Modele danych

### User

```
id: UUID (PK)
email: str (unique)
hashed_password: str
full_name: str | None
avatar_url: str | None
created_at: datetime
updated_at: datetime
```

### RefreshToken

```
id: UUID (PK)
user_id: UUID (FK → users)
token_hash: str (unique)
expires_at: datetime
revoked_at: datetime | None
created_at: datetime
```

### Organization

```
id: UUID (PK)
name: str
slug: str (unique)
description: str | None
created_by: UUID (FK → users)
created_at: datetime
updated_at: datetime
```

### OrganizationMember

```
id: UUID (PK)
org_id: UUID (FK → organizations)
user_id: UUID (FK → users)
role: Enum('owner', 'admin', 'member')
joined_at: datetime
```

### Project

```
id: UUID (PK)
org_id: UUID (FK → organizations) | None
name: str
description: str | None
status: Enum('active', 'archived')
github_repo_url: str | None
created_by: UUID (FK → users)
created_at: datetime
updated_at: datetime
```

### Task

```
id: UUID (PK)
project_id: UUID (FK → projects) | None
title: str
description: str | None
status: Enum('backlog', 'todo', 'in_progress', 'review', 'done', 'cancelled')
priority: Enum('low', 'medium', 'high', 'critical')
estimate_minutes: int | None
assignee_id: UUID (FK → users) | None
created_by: UUID (FK → users)
due_date: date | None
source: Enum('manual', 'github_pr', 'github_issue')
github_url: str | None
created_at: datetime
updated_at: datetime
```

### WorkSession

```
id: UUID (PK)
task_id: UUID (FK → tasks)
user_id: UUID (FK → users)
started_at: datetime
ended_at: datetime | None
duration_minutes: int | None   ← wypełniane automatycznie przy stop
created_at: datetime
```

### Report

```
id: UUID (PK)
user_id: UUID (FK → users)
type: Enum('weekly_summary', 'project_status', 'productivity_overview')
format: Enum('json', 'csv', 'pdf')
status: Enum('pending', 'generating', 'ready', 'failed')
payload: JSON | None           ← dla format='json'
file_url: str | None           ← dla format='csv'/'pdf'
generated_at: datetime | None
created_at: datetime
```

### GitHubConnection

```
id: UUID (PK)
user_id: UUID (FK → users, unique)
github_user_id: int
github_username: str
access_token_encrypted: bytes  ← szyfrowany Fernet
scopes: str                    ← np. "repo,read:user"
connected_at: datetime
last_sync_at: datetime | None
```

## Schemat bazy danych (relacje)

```
users ──────────────────────────────────────────────────────────┐
  │                                                             │
  ├─< refresh_tokens                                            │
  ├─< organization_members >─── organizations                   │
  ├─< projects (created_by)                                     │
  ├─< tasks (assignee_id, created_by)                          │
  ├─< work_sessions                                             │
  ├─< reports                                                   │
  └─< github_connections                                        │
                                                                │
organizations ──< projects ──< tasks ──< work_sessions          │
```

## Specyfikacja endpointów

### Health & Status

| Metoda | Ścieżka | Opis | Status |
|---|---|---|---|
| GET | `/health` | Health check | ✅ Zaimplementowane |
| GET | `/api/v1` | API status | ✅ Zaimplementowane |

### Auth (`/api/v1/auth`)

| Metoda | Ścieżka | Opis | Auth |
|---|---|---|---|
| POST | `/api/v1/auth/register` | Rejestracja | Nie |
| POST | `/api/v1/auth/login` | Logowanie → JWT tokens | Nie |
| POST | `/api/v1/auth/refresh` | Odnowienie access token | Refresh token |
| POST | `/api/v1/auth/logout` | Wylogowanie | Bearer |
| GET | `/api/v1/auth/me` | Profil użytkownika | Bearer |
| PATCH | `/api/v1/auth/me` | Aktualizacja profilu | Bearer |

### Organizations (`/api/v1/organizations`)

| Metoda | Ścieżka | Opis | Rola |
|---|---|---|---|
| POST | `/api/v1/organizations` | Utwórz org | Zalogowany |
| GET | `/api/v1/organizations` | Lista moich org | Zalogowany |
| GET | `/api/v1/organizations/{org_id}` | Szczegóły org | Member |
| PATCH | `/api/v1/organizations/{org_id}` | Aktualizuj org | Admin/Owner |
| DELETE | `/api/v1/organizations/{org_id}` | Usuń org (soft) | Owner |
| POST | `/api/v1/organizations/{org_id}/members` | Zaproś membera | Admin/Owner |
| GET | `/api/v1/organizations/{org_id}/members` | Lista memberów | Member |
| DELETE | `/api/v1/organizations/{org_id}/members/{user_id}` | Usuń membera | Admin/Owner |

### Projects (`/api/v1/projects`)

| Metoda | Ścieżka | Opis | Auth |
|---|---|---|---|
| POST | `/api/v1/projects` | Utwórz projekt | Bearer |
| GET | `/api/v1/projects` | Lista projektów | Bearer |
| GET | `/api/v1/projects/{project_id}` | Szczegóły projektu | Bearer |
| PATCH | `/api/v1/projects/{project_id}` | Aktualizuj projekt | Bearer |
| DELETE | `/api/v1/projects/{project_id}` | Archiwizuj projekt | Bearer |

Parametry query dla GET `/api/v1/projects`: `org_id`, `status`, `limit`, `offset`.

### Tasks (`/api/v1/tasks`)

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

Parametry query dla GET `/api/v1/tasks`: `project_id`, `status`, `priority`, `assignee_id`, `limit`, `offset`.

### Metrics (`/api/v1/metrics`)

| Metoda | Ścieżka | Opis | Auth |
|---|---|---|---|
| GET | `/api/v1/metrics/summary` | Podsumowanie produktywności | Bearer |
| GET | `/api/v1/metrics/velocity` | Velocity (taski/tydzień) | Bearer |
| GET | `/api/v1/metrics/time-tracking` | Czas pracy dzienny | Bearer |
| GET | `/api/v1/metrics/completion-rate` | % ukończonych tasków | Bearer |
| GET | `/api/v1/metrics/estimation-accuracy` | Dokładność estymacji | Bearer |
| GET | `/api/v1/metrics/streaks` | Streaki aktywności | Bearer |
| GET | `/api/v1/metrics/projects/{project_id}` | Metryki projektu | Bearer |

Parametry query (wspólne): `date_from` (ISO 8601), `date_to` (ISO 8601), `org_id`.

### Reports (`/api/v1/reports`)

| Metoda | Ścieżka | Opis | Auth |
|---|---|---|---|
| POST | `/api/v1/reports` | Wygeneruj raport | Bearer |
| GET | `/api/v1/reports` | Lista raportów | Bearer |
| GET | `/api/v1/reports/{report_id}` | Pobierz raport | Bearer |
| DELETE | `/api/v1/reports/{report_id}` | Usuń raport | Bearer |

### GitHub Integration (`/api/v1/integrations/github`)

| Metoda | Ścieżka | Opis | Auth |
|---|---|---|---|
| POST | `/api/v1/integrations/github/authorize` | Inicjuj OAuth flow | Bearer |
| GET | `/api/v1/integrations/github/callback` | OAuth callback | — |
| GET | `/api/v1/integrations/github/status` | Status połączenia | Bearer |
| DELETE | `/api/v1/integrations/github/disconnect` | Odłącz GitHub | Bearer |
| POST | `/api/v1/integrations/github/sync` | Ręczna synchronizacja | Bearer |
| POST | `/api/v1/integrations/github/webhooks` | Webhook receiver | HMAC |

## Authentication Flow

```
1. POST /auth/register → 201 Created
2. POST /auth/login → { access_token, refresh_token, expires_in }
3. Każdy request: Authorization: Bearer <access_token>
4. Gdy access_token wygaśnie (TTL 15 min):
   POST /auth/refresh { refresh_token } → { access_token, expires_in }
5. POST /auth/logout → unieważnia refresh_token w bazie
```

## Format odpowiedzi

### Sukces

```json
{
  "data": { ... },
  "meta": { "total": 42, "limit": 20, "offset": 0 }
}
```

Dla operacji bez paginacji `meta` jest pomijane.

### Błąd

```json
{
  "error": {
    "code": "VALIDATION_ERROR",
    "message": "Nieprawidłowe dane wejściowe",
    "details": { "email": "Nieprawidłowy format adresu email" }
  }
}
```

## Konwencje kodowania

- **Typy:** Ścisłe typowanie, mypy strict — zero `Any` bez uzasadnienia
- **Async:** Wszystkie route handlery i operacje bazodanowe async/await
- **Walidacja:** Pydantic v2 na wszystkich inputach; oddzielne schematy Request vs Response
- **Błędy:** `AppError` z kodem, wiadomością i statusem HTTP; nie łapać generic Exception
- **Nazewnictwo:** snake_case dla zmiennych/funkcji, PascalCase dla klas, SCREAMING_SNAKE dla stałych
- **Testy:** Każdy serwis testowany jednostkowo, każdy endpoint testowany integracyjnie
