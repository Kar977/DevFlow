# Services

Logika biznesowa i orchestracja przypadków użycia.

## Zasady

- Serwis nie zna FastAPI — brak importów z `fastapi` (poza typami jeśli konieczne).
- Serwis przyjmuje repozytoria przez konstruktor (dependency injection).
- Serwis koordynuje: repozytoria, inne serwisy, integracje zewnętrzne.
- Każdy serwis w osobnym pliku.
- Serwis jest testowalny bez TestClient — testowany jednostkowo z mock repozytoriami.

## Wzorzec implementacji

```python
class AuthService:
    def __init__(
        self,
        user_repo: UserRepository,
        token_repo: RefreshTokenRepository,
    ) -> None:
        self._user_repo = user_repo
        self._token_repo = token_repo

    async def register(self, email: str, password: str, full_name: str | None) -> User:
        if await self._user_repo.exists_by_email(email):
            raise AppError(code="EMAIL_TAKEN", message="Email already registered", status_code=409)
        hashed = hash_password(password)
        return await self._user_repo.create(email=email, hashed_password=hashed, full_name=full_name)
```

## Serwisy do zaimplementowania

### `auth.py` — `AuthService`

Odpowiedzialność: rejestracja, autentykacja, zarządzanie tokenami JWT.

```python
async def register(email, password, full_name) -> User
    # Sprawdź unikalność emaila
    # Hash hasła (bcrypt, cost=12)
    # Utwórz użytkownika

async def authenticate(email, password) -> tuple[str, str]
    # Pobierz użytkownika po emailu
    # Zweryfikuj hasło (bcrypt verify)
    # Wygeneruj access_token (JWT, TTL 15 min)
    # Wygeneruj refresh_token (opaque token, TTL 30 dni, hash w bazie)
    # Zwróć (access_token, refresh_token)

async def refresh(refresh_token: str) -> str
    # Hash tokenu → pobierz z bazy
    # Sprawdź czy nie wygasł i nie unieważniony
    # Wygeneruj nowy access_token
    # Zwróć access_token

async def revoke(refresh_token: str) -> None
    # Hash tokenu → oznacz jako revoked w bazie

async def get_current_user(user_id: UUID) -> User
    # Pobierz użytkownika po ID (z tokenu JWT)

async def update_profile(user_id: UUID, full_name, avatar_url) -> User
```

Biblioteki: `python-jose[cryptography]` lub `PyJWT` dla JWT, `passlib[bcrypt]` dla haseł.

---

### `organization.py` — `OrganizationService`

```python
async def create(name: str, created_by: UUID) -> Organization
    # Generuj slug z nazwy (slugify)
    # Sprawdź unikalność sluga
    # Utwórz org
    # Dodaj creatora jako 'owner'

async def get(org_id: UUID, requester_id: UUID) -> Organization
    # Sprawdź membership

async def list_for_user(user_id: UUID) -> list[Organization]

async def update(org_id: UUID, requester_id: UUID, **fields) -> Organization
    # Sprawdź role (admin/owner)

async def delete(org_id: UUID, requester_id: UUID) -> None
    # Sprawdź rolę (owner)
    # Soft delete

async def invite_member(org_id: UUID, email: str, role: str, requester_id: UUID) -> OrganizationMember
    # Sprawdź rolę requestera (admin/owner)
    # Znajdź user po emailu (lub zwróć błąd)
    # Dodaj membership

async def remove_member(org_id: UUID, user_id: UUID, requester_id: UUID) -> None
    # Sprawdź rolę requestera
    # Nie można usunąć jedynego ownera
```

---

### `project.py` — `ProjectService`

```python
async def create(name: str, created_by: UUID, org_id: UUID | None, **kwargs) -> Project
    # Jeśli org_id podane: sprawdź membership w org
    # Utwórz projekt

async def get(project_id: UUID, requester_id: UUID) -> Project
    # Sprawdź dostęp (owner lub org member)

async def list(user_id: UUID, **filters) -> tuple[list[Project], int]

async def update(project_id: UUID, requester_id: UUID, **fields) -> Project

async def archive(project_id: UUID, requester_id: UUID) -> None

async def get_stats(project_id: UUID) -> ProjectStats
    # total_tasks, open_tasks, overdue_tasks, completion_rate
    # Używa TaskRepository.count_by_status + TaskRepository.list_overdue
```

---

### `task.py` — `TaskService`

Odpowiedzialność: CRUD tasków + time tracking (start/stop sesji pracy).

```python
async def create(title: str, created_by: UUID, **kwargs) -> Task

async def get(task_id: UUID, requester_id: UUID) -> Task

async def list(requester_id: UUID, **filters) -> tuple[list[Task], int]

async def update(task_id: UUID, requester_id: UUID, **fields) -> Task

async def delete(task_id: UUID, requester_id: UUID) -> None

async def start_session(task_id: UUID, user_id: UUID) -> WorkSession
    # Sprawdź czy nie ma aktywnej sesji dla tego usera
    # Jeśli task ma status 'backlog'/'todo' → zmień na 'in_progress'
    # Utwórz WorkSession

async def stop_session(task_id: UUID, user_id: UUID) -> WorkSession
    # Znajdź aktywną sesję
    # Oblicz duration_minutes = (now - started_at).seconds // 60
    # Zaktualizuj sesję (ended_at, duration_minutes)

async def list_sessions(task_id: UUID) -> list[WorkSession]
```

---

### `metrics.py` — `MetricsService`

Odpowiedzialność: obliczanie wszystkich metryk produktywności.

```python
async def get_summary(user_id: UUID, date_from: date, date_to: date) -> MetricsSummary
    # Zbiera wszystkie metryki: velocity, completion_rate, total_work_hours,
    # estimation_accuracy, current_streak
    # Porównuje z poprzednim równoważnym okresem (delta %)

async def get_velocity(user_id: UUID, weeks: int = 8) -> VelocityData
    # Liczba ukończonych tasków per tydzień z trendem
    # Używa TaskRepository.list_completed_by_week

async def get_time_tracking(user_id: UUID, date_from: date, date_to: date) -> TimeTrackingData
    # Godziny pracy per dzień
    # Używa WorkSessionRepository.sum_minutes_by_day

async def get_completion_rate(user_id: UUID, date_from: date, date_to: date) -> float
    # done / (done + cancelled + open) * 100

async def get_estimation_accuracy(user_id: UUID, date_from: date, date_to: date) -> AccuracyData
    # Dla tasków done z estimate_minutes: actual/estimate ratio
    # Kategorie: under_estimated, accurate, over_estimated

async def get_streaks(user_id: UUID) -> StreakData
    # current_streak: ile kolejnych dni z >= 1 done task
    # longest_streak: rekordowa seria

async def get_project_metrics(project_id: UUID, requester_id: UUID) -> ProjectMetrics
```

**Cachowanie:** Wyniki `get_summary` i `get_velocity` powinny być cachowane przez 5 minut. Na starcie implementuj prostym `functools.lru_cache` z TTL lub słownikiem; Redis jako kolejny krok.

---

### `report.py` — `ReportService`

```python
async def request(user_id: UUID, type: str, format: str, **params) -> Report
    # Utwórz rekord Report ze statusem 'pending'
    # Enqueue background task (FastAPI BackgroundTasks)
    # Zwróć Report

async def generate(report_id: UUID) -> None   ← background task
    # Zmień status na 'generating'
    # Zbierz dane (MetricsService / TaskRepository)
    # Serializuj do JSON / CSV
    # Zaktualizuj Report (status='ready', payload lub file_url)
    # W razie błędu: status='failed', error_message

async def get(report_id: UUID, requester_id: UUID) -> Report

async def list(user_id: UUID, **pagination) -> tuple[list[Report], int]

async def delete(report_id: UUID, requester_id: UUID) -> None
```

---

### `github_sync.py` — `GitHubSyncService`

```python
async def start_oauth(user_id: UUID) -> str
    # Generuj state (CSRF token), zapisz w sesji/cache
    # Zwróć URL autoryzacji GitHub OAuth

async def complete_oauth(code: str, state: str) -> GitHubConnection
    # Zweryfikuj state
    # Wymień code na access_token (GitHubOAuthClient)
    # Pobierz profil GitHub usera
    # Zaszyfruj token (Fernet)
    # Zapisz GitHubConnection

async def disconnect(user_id: UUID) -> None
    # Usuń GitHubConnection
    # Opcjonalnie: cofnij token w GitHub API

async def sync(user_id: UUID) -> SyncResult
    # Pobierz GitHubConnection
    # Przez GitHubClient pobierz PR i Issues
    # Utwórz/aktualizuj Taski z source='github_pr'/'github_issue'
    # Zaktualizuj last_sync_at

async def handle_webhook(payload: dict, signature: str) -> None
    # Zweryfikuj HMAC-SHA256 signature
    # Parsuj event type (pull_request, issues)
    # Dla PR.opened/closed/merged: utwórz/aktualizuj Task
    # Dla issues.opened/closed: utwórz/aktualizuj Task
```
