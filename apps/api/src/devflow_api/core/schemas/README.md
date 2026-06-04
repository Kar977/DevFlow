# Schemas

Pydantic v2 models for request/response API contracts.

## Rules

- Separate schemas for request and response — never reuse the same model for both.
- Each domain in its own subdirectory (`auth/`, `organizations/`, `tasks/`, etc.).
- Response schemas do not expose sensitive fields (e.g. `hashed_password`).
- Use `model_config = ConfigDict(from_attributes=True)` in response schemas (ORM mapping).
- Optional fields in PATCH requests as `T | None = None`.

## Implementation Pattern

```python
# Request — input validation
class CreateTaskRequest(BaseModel):
    title: str = Field(min_length=1, max_length=255)
    description: str | None = None
    priority: Literal['low', 'medium', 'high', 'critical'] = 'medium'
    estimate_minutes: int | None = Field(None, ge=1, le=480)

# Response — output contract
class TaskResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    title: str
    status: str
    priority: str
    created_at: datetime
```

## Schemas to Implement

### `auth/`

```python
# requests
class RegisterRequest(BaseModel):
    email: EmailStr
    password: str  # Field(min_length=8, max_length=100)
    full_name: str | None = None

class LoginRequest(BaseModel):
    email: EmailStr
    password: str

class RefreshRequest(BaseModel):
    refresh_token: str

class UpdateProfileRequest(BaseModel):
    full_name: str | None = None
    avatar_url: AnyHttpUrl | None = None

# responses
class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int  # seconds

class AccessTokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int

class UserResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    email: str
    full_name: str | None
    avatar_url: str | None
    created_at: datetime
```

---

### `organizations/`

```python
# requests
class CreateOrganizationRequest(BaseModel):
    name: str  # Field(min_length=1, max_length=100)
    description: str | None = None

class UpdateOrganizationRequest(BaseModel):
    name: str | None = None
    description: str | None = None

class InviteMemberRequest(BaseModel):
    email: EmailStr
    role: Literal['admin', 'member'] = 'member'

# responses
class OrganizationResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    name: str
    slug: str
    description: str | None
    created_at: datetime

class MemberResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    user_id: UUID
    role: str
    joined_at: datetime
    user: UserResponse  # nested
```

---

### `projects/`

```python
# requests
class CreateProjectRequest(BaseModel):
    name: str  # Field(min_length=1, max_length=100)
    description: str | None = None
    org_id: UUID | None = None
    github_repo_url: AnyHttpUrl | None = None

class UpdateProjectRequest(BaseModel):
    name: str | None = None
    description: str | None = None
    status: Literal['active', 'archived'] | None = None
    github_repo_url: AnyHttpUrl | None = None

# responses
class ProjectResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    name: str
    description: str | None
    status: str
    github_repo_url: str | None
    created_at: datetime

class ProjectStatsResponse(BaseModel):
    total_tasks: int
    open_tasks: int
    overdue_tasks: int
    completion_rate: float
```

---

### `tasks/`

```python
# requests
class CreateTaskRequest(BaseModel):
    title: str  # Field(min_length=1, max_length=255)
    description: str | None = None
    project_id: UUID | None = None
    priority: Literal['low', 'medium', 'high', 'critical'] = 'medium'
    estimate_minutes: int | None = Field(None, ge=1, le=28800)
    assignee_id: UUID | None = None
    due_date: date | None = None

class UpdateTaskRequest(BaseModel):
    title: str | None = None
    description: str | None = None
    status: Literal['backlog', 'todo', 'in_progress', 'review', 'done', 'cancelled'] | None = None
    priority: Literal['low', 'medium', 'high', 'critical'] | None = None
    estimate_minutes: int | None = None
    assignee_id: UUID | None = None
    due_date: date | None = None

# responses
class TaskResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    title: str
    description: str | None
    status: str
    priority: str
    estimate_minutes: int | None
    assignee_id: UUID | None
    project_id: UUID | None
    due_date: date | None
    source: str
    github_url: str | None
    created_at: datetime
    updated_at: datetime

class WorkSessionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    task_id: UUID
    started_at: datetime
    ended_at: datetime | None
    duration_minutes: int | None
```

---

### `metrics/`

```python
class MetricValue(BaseModel):
    value: float
    previous_value: float | None = None
    delta_percent: float | None = None  # (value - previous) / previous * 100

class VelocityPoint(BaseModel):
    week_start: date
    tasks_completed: int

class VelocityResponse(BaseModel):
    current_week: int
    data: list[VelocityPoint]  # last N weeks
    trend: Literal['up', 'down', 'stable']

class TimeTrackingPoint(BaseModel):
    date: date
    minutes: int

class TimeTrackingResponse(BaseModel):
    data: list[TimeTrackingPoint]
    total_hours: float

class EstimationAccuracyResponse(BaseModel):
    ratio: float  # actual / estimate
    category: Literal['accurate', 'under_estimated', 'over_estimated']
    tasks_analyzed: int

class StreakResponse(BaseModel):
    current_streak: int
    longest_streak: int

class MetricsSummaryResponse(BaseModel):
    velocity: MetricValue       # tasks/week
    completion_rate: MetricValue # %
    active_hours_per_day: MetricValue
    current_streak: int
    date_from: date
    date_to: date
```

---

### `reports/`

```python
class CreateReportRequest(BaseModel):
    type: Literal['weekly_summary', 'project_status', 'productivity_overview']
    format: Literal['json', 'csv'] = 'json'
    project_id: UUID | None = None     # required for type='project_status'
    date_from: date | None = None
    date_to: date | None = None

class ReportResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    type: str
    format: str
    status: str
    payload: dict | None = None
    file_url: str | None = None
    generated_at: datetime | None
    created_at: datetime
```

---

### `github/`

```python
class GitHubConnectionResponse(BaseModel):
    github_username: str
    scopes: list[str]
    connected_at: datetime
    last_sync_at: datetime | None

class AuthorizeResponse(BaseModel):
    authorization_url: str

class SyncResultResponse(BaseModel):
    tasks_created: int
    tasks_updated: int
    synced_at: datetime
```
