# GitHub Integration

GitHub API client, OAuth flow, webhook handling, and sync logic.

## Rules

- Route handlers call services; they do not reach into integration clients directly.
- All GitHub API communication is encapsulated in this module.
- Access tokens are stored in the database **encrypted** (Fernet symmetric encryption).

## Modules to Implement

### `client.py` — `GitHubClient`

Async HTTP client for GitHub REST API v3 using `httpx.AsyncClient`.

```python
class GitHubClient:
    BASE_URL = "https://api.github.com"

    def __init__(self, access_token: str) -> None:
        self._token = access_token

    async def get_user(self) -> dict
        # GET /user — authenticated user profile

    async def list_repos(self, page: int = 1, per_page: int = 100) -> list[dict]
        # GET /user/repos — list repositories

    async def list_pull_requests(self, owner: str, repo: str, state: str = "all") -> list[dict]
        # GET /repos/{owner}/{repo}/pulls

    async def list_issues(self, owner: str, repo: str, state: str = "all") -> list[dict]
        # GET /repos/{owner}/{repo}/issues

    async def _request(self, method: str, path: str, **kwargs) -> dict
        # Set Authorization header
        # Handle rate limiting (X-RateLimit-Remaining, X-RateLimit-Reset)
        # Retry on 429 with exponential backoff
        # Raise AppError on HTTP errors
```

### `oauth.py` — `GitHubOAuthClient`

GitHub OAuth App flow handling.

```python
GITHUB_AUTHORIZE_URL = "https://github.com/login/oauth/authorize"
GITHUB_TOKEN_URL = "https://github.com/login/oauth/access_token"

REQUIRED_SCOPES = ["repo", "read:user", "read:org"]

def build_authorization_url(state: str, client_id: str) -> str
    # Build URL for redirecting user to GitHub
    # Params: client_id, redirect_uri, scope, state

async def exchange_code_for_token(code: str, client_id: str, client_secret: str) -> dict
    # POST to GITHUB_TOKEN_URL
    # Returns: access_token, token_type, scope
    # Raise error when code is expired or invalid
```

Configuration via environment variables:
- `DEVFLOW_API_GITHUB_CLIENT_ID`
- `DEVFLOW_API_GITHUB_CLIENT_SECRET`
- `DEVFLOW_API_GITHUB_REDIRECT_URI` (e.g. `http://localhost:8000/api/v1/integrations/github/callback`)

### `webhooks.py` — verification and event parsing

```python
def verify_signature(payload: bytes, signature: str, secret: str) -> bool
    # HMAC-SHA256 verification
    # signature format: "sha256=<hex_digest>"
    # Use hmac.compare_digest (timing-safe)

def parse_event(event_type: str, payload: dict) -> WebhookEvent | None
    # event_type from X-GitHub-Event header
    # Supported types:
    #   "pull_request" — action: opened, closed, merged, reopened
    #   "issues"       — action: opened, closed, reopened
    # Returns None for unsupported events

@dataclass
class WebhookEvent:
    event_type: str          # "pull_request" | "issue"
    action: str              # "opened" | "closed" | "merged"
    external_id: int         # GitHub PR/issue ID
    title: str
    url: str
    state: str               # "open" | "closed"
    repo_full_name: str      # "owner/repo"
```

The `X-Hub-Signature-256` header must be verified **before** parsing the payload.

### `sync.py` — `GitHubSyncRunner`

GitHub data → DevFlow tasks synchronization logic.

```python
class GitHubSyncRunner:
    def __init__(self, client: GitHubClient, task_repo: TaskRepository) -> None:
        ...

    async def sync_pull_requests(self, owner: str, repo: str) -> SyncStats
        # Fetch PRs from GitHub
        # For each PR: upsert Task (source='github_pr')
        # Status mapping: open→in_progress, closed+merged→done, closed→cancelled

    async def sync_issues(self, owner: str, repo: str) -> SyncStats
        # Fetch Issues from GitHub
        # For each Issue: upsert Task (source='github_issue')
        # Status mapping: open→todo, closed→done

    async def handle_webhook_event(self, event: WebhookEvent, user_id: UUID) -> None
        # Find or create Task by event.external_id + repo
        # Update status based on event.action

@dataclass
class SyncStats:
    tasks_created: int
    tasks_updated: int
    errors: int
```

## Token Encryption

GitHub tokens are stored in the `access_token_encrypted` column (bytes).

```python
from cryptography.fernet import Fernet

# Key from config: DEVFLOW_API_ENCRYPTION_KEY (base64-encoded 32 bytes)
def encrypt_token(token: str, key: str) -> bytes:
    return Fernet(key).encrypt(token.encode())

def decrypt_token(encrypted: bytes, key: str) -> str:
    return Fernet(key).decrypt(encrypted).decode()
```

Required dependency: `cryptography>=43.0` (add to `pyproject.toml`).

## Environment Variables

| Variable | Description |
|---|---|
| `DEVFLOW_API_GITHUB_CLIENT_ID` | GitHub OAuth App Client ID |
| `DEVFLOW_API_GITHUB_CLIENT_SECRET` | GitHub OAuth App Client Secret |
| `DEVFLOW_API_GITHUB_REDIRECT_URI` | Callback URL after authorization |
| `DEVFLOW_API_GITHUB_WEBHOOK_SECRET` | Secret for HMAC webhook verification |
| `DEVFLOW_API_ENCRYPTION_KEY` | Fernet key for token encryption |
