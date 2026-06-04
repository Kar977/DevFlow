# Services

Business logic and use case orchestration.

## Rules

- Services do not know about FastAPI — no imports from `fastapi` (except types if unavoidable).
- Services receive repositories via constructor (dependency injection).
- Services coordinate: repositories, other services, external integrations.
- Each service in its own file.
- Services are testable without TestClient — unit-tested with mock repositories.

## Implementation Pattern

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

## Services to Implement

### `auth.py` — `AuthService`

Responsibility: registration, authentication, JWT token management.

```python
async def register(email, password, full_name) -> User
    # Check email uniqueness
    # Hash password (bcrypt, cost=12)
    # Create user

async def authenticate(email, password) -> tuple[str, str]
    # Fetch user by email
    # Verify password (bcrypt verify)
    # Generate access_token (JWT, TTL 15 min)
    # Generate refresh_token (opaque token, TTL 30 days, hash stored in DB)
    # Return (access_token, refresh_token)

async def refresh(refresh_token: str) -> str
    # Hash token → fetch from DB
    # Check not expired and not revoked
    # Generate new access_token
    # Return access_token

async def revoke(refresh_token: str) -> None
    # Hash token → mark as revoked in DB

async def get_current_user(user_id: UUID) -> User
    # Fetch user by ID (from JWT payload)

async def update_profile(user_id: UUID, full_name, avatar_url) -> User
```

Libraries: `python-jose[cryptography]` or `PyJWT` for JWT, `passlib[bcrypt]` for passwords.

---

### `organization.py` — `OrganizationService`

```python
async def create(name: str, created_by: UUID) -> Organization
    # Generate slug from name (slugify)
    # Check slug uniqueness
    # Create org
    # Add creator as 'owner'

async def get(org_id: UUID, requester_id: UUID) -> Organization
    # Check membership

async def list_for_user(user_id: UUID) -> list[Organization]

async def update(org_id: UUID, requester_id: UUID, **fields) -> Organization
    # Check role (admin/owner)

async def delete(org_id: UUID, requester_id: UUID) -> None
    # Check role (owner)
    # Soft delete

async def invite_member(org_id: UUID, email: str, role: str, requester_id: UUID) -> OrganizationMember
    # Check requester role (admin/owner)
    # Find user by email (or raise error)
    # Add membership

async def remove_member(org_id: UUID, user_id: UUID, requester_id: UUID) -> None
    # Check requester role
    # Cannot remove the sole owner
```

---

### `project.py` — `ProjectService`

```python
async def create(name: str, created_by: UUID, org_id: UUID | None, **kwargs) -> Project
    # If org_id provided: verify membership in org
    # Create project

async def get(project_id: UUID, requester_id: UUID) -> Project
    # Check access (owner or org member)

async def list(user_id: UUID, **filters) -> tuple[list[Project], int]

async def update(project_id: UUID, requester_id: UUID, **fields) -> Project

async def archive(project_id: UUID, requester_id: UUID) -> None

async def get_stats(project_id: UUID) -> ProjectStats
    # total_tasks, open_tasks, overdue_tasks, completion_rate
    # Uses TaskRepository.count_by_status + TaskRepository.list_overdue
```

---

### `task.py` — `TaskService`

Responsibility: task CRUD + time tracking (start/stop work sessions).

```python
async def create(title: str, created_by: UUID, **kwargs) -> Task

async def get(task_id: UUID, requester_id: UUID) -> Task

async def list(requester_id: UUID, **filters) -> tuple[list[Task], int]

async def update(task_id: UUID, requester_id: UUID, **fields) -> Task

async def delete(task_id: UUID, requester_id: UUID) -> None

async def start_session(task_id: UUID, user_id: UUID) -> WorkSession
    # Check no active session exists for this user
    # If task status is 'backlog'/'todo' → change to 'in_progress'
    # Create WorkSession

async def stop_session(task_id: UUID, user_id: UUID) -> WorkSession
    # Find active session
    # Calculate duration_minutes = (now - started_at).seconds // 60
    # Update session (ended_at, duration_minutes)

async def list_sessions(task_id: UUID) -> list[WorkSession]
```

---

### `metrics.py` — `MetricsService`

Responsibility: compute all productivity metrics.

```python
async def get_summary(user_id: UUID, date_from: date, date_to: date) -> MetricsSummary
    # Collects all metrics: velocity, completion_rate, total_work_hours,
    # estimation_accuracy, current_streak
    # Compares to the previous equivalent period (delta %)

async def get_velocity(user_id: UUID, weeks: int = 8) -> VelocityData
    # Completed tasks per week with trend
    # Uses TaskRepository.list_completed_by_week

async def get_time_tracking(user_id: UUID, date_from: date, date_to: date) -> TimeTrackingData
    # Work hours per day
    # Uses WorkSessionRepository.sum_minutes_by_day

async def get_completion_rate(user_id: UUID, date_from: date, date_to: date) -> float
    # done / (done + cancelled + open) * 100

async def get_estimation_accuracy(user_id: UUID, date_from: date, date_to: date) -> AccuracyData
    # For done tasks with estimate_minutes: actual/estimate ratio
    # Categories: under_estimated, accurate, over_estimated

async def get_streaks(user_id: UUID) -> StreakData
    # current_streak: consecutive days with >= 1 done task
    # longest_streak: all-time record

async def get_project_metrics(project_id: UUID, requester_id: UUID) -> ProjectMetrics
```

**Caching:** Results of `get_summary` and `get_velocity` should be cached for 5 minutes. Start with a simple in-memory dict with TTL; add Redis as a next step.

---

### `report.py` — `ReportService`

```python
async def request(user_id: UUID, type: str, format: str, **params) -> Report
    # Create Report record with status 'pending'
    # Enqueue background task (FastAPI BackgroundTasks)
    # Return Report

async def generate(report_id: UUID) -> None   ← background task
    # Change status to 'generating'
    # Gather data (MetricsService / TaskRepository)
    # Serialize to JSON / CSV
    # Update Report (status='ready', payload or file_url)
    # On error: status='failed', error_message

async def get(report_id: UUID, requester_id: UUID) -> Report

async def list(user_id: UUID, **pagination) -> tuple[list[Report], int]

async def delete(report_id: UUID, requester_id: UUID) -> None
```

---

### `github_sync.py` — `GitHubSyncService`

```python
async def start_oauth(user_id: UUID) -> str
    # Generate state (CSRF token), save in cache/session
    # Return GitHub OAuth authorization URL

async def complete_oauth(code: str, state: str) -> GitHubConnection
    # Verify state
    # Exchange code for access_token (GitHubOAuthClient)
    # Fetch GitHub user profile
    # Encrypt token (Fernet)
    # Save GitHubConnection

async def disconnect(user_id: UUID) -> None
    # Delete GitHubConnection
    # Optionally: revoke token via GitHub API

async def sync(user_id: UUID) -> SyncResult
    # Fetch GitHubConnection
    # Fetch PRs and Issues via GitHubClient
    # Create/update Tasks with source='github_pr'/'github_issue'
    # Update last_sync_at

async def handle_webhook(payload: dict, signature: str) -> None
    # Verify HMAC-SHA256 signature
    # Parse event type (pull_request, issues)
    # For PR.opened/closed/merged: create/update Task
    # For issues.opened/closed: create/update Task
```
