# GitHub Integration

Klient GitHub API, OAuth flow, obsługa webhooków i logika synchronizacji.

## Zasady

- Route handlery wywołują serwisy, nie sięgają bezpośrednio do klientów integracji.
- Cała logika komunikacji z GitHub API zamknięta w tym module.
- Tokeny dostępu przechowywane w bazie **zaszyfrowane** (Fernet symmetric encryption).

## Moduły do zaimplementowania

### `client.py` — `GitHubClient`

Async HTTP klient do GitHub REST API v3 przy użyciu `httpx.AsyncClient`.

```python
class GitHubClient:
    BASE_URL = "https://api.github.com"

    def __init__(self, access_token: str) -> None:
        self._token = access_token

    async def get_user(self) -> dict
        # GET /user — profil zalogowanego użytkownika

    async def list_repos(self, page: int = 1, per_page: int = 100) -> list[dict]
        # GET /user/repos — lista repozytoriów

    async def list_pull_requests(self, owner: str, repo: str, state: str = "all") -> list[dict]
        # GET /repos/{owner}/{repo}/pulls

    async def list_issues(self, owner: str, repo: str, state: str = "all") -> list[dict]
        # GET /repos/{owner}/{repo}/issues

    async def _request(self, method: str, path: str, **kwargs) -> dict
        # Obsługa nagłówków autoryzacji
        # Obsługa rate limiting (X-RateLimit-Remaining, X-RateLimit-Reset)
        # Retry przy 429 z exponential backoff
        # Raise AppError przy błędach HTTP
```

### `oauth.py` — `GitHubOAuthClient`

Obsługa GitHub OAuth App flow.

```python
GITHUB_AUTHORIZE_URL = "https://github.com/login/oauth/authorize"
GITHUB_TOKEN_URL = "https://github.com/login/oauth/access_token"

REQUIRED_SCOPES = ["repo", "read:user", "read:org"]

def build_authorization_url(state: str, client_id: str) -> str
    # Buduje URL do przekierowania usera na GitHub
    # Parametry: client_id, redirect_uri, scope, state

async def exchange_code_for_token(code: str, client_id: str, client_secret: str) -> dict
    # POST do GITHUB_TOKEN_URL
    # Zwraca: access_token, token_type, scope
    # Błąd gdy code wygasł lub nieprawidłowy
```

Konfiguracja przez zmienne środowiskowe:
- `DEVFLOW_API_GITHUB_CLIENT_ID`
- `DEVFLOW_API_GITHUB_CLIENT_SECRET`
- `DEVFLOW_API_GITHUB_REDIRECT_URI` (np. `http://localhost:8000/api/v1/integrations/github/callback`)

### `webhooks.py` — weryfikacja i parsowanie webhooków

```python
def verify_signature(payload: bytes, signature: str, secret: str) -> bool
    # HMAC-SHA256 weryfikacja
    # signature format: "sha256=<hex_digest>"
    # Używaj hmac.compare_digest (timing-safe)

def parse_event(event_type: str, payload: dict) -> WebhookEvent | None
    # event_type z nagłówka X-GitHub-Event
    # Obsługiwane typy:
    #   "pull_request" — action: opened, closed, merged, reopened
    #   "issues"       — action: opened, closed, reopened
    # Zwraca None dla nieobsługiwanych eventów

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

Nagłówek `X-Hub-Signature-256` musi być weryfikowany **przed** parsowaniem payload.

### `sync.py` — `GitHubSyncRunner`

Logika synchronizacji danych GitHub → taski DevFlow.

```python
class GitHubSyncRunner:
    def __init__(self, client: GitHubClient, task_repo: TaskRepository) -> None:
        ...

    async def sync_pull_requests(self, owner: str, repo: str) -> SyncStats
        # Pobierz PR z GitHub
        # Dla każdego PR: upsert Task (source='github_pr')
        # Mapowanie statusów: open→in_progress, closed+merged→done, closed→cancelled

    async def sync_issues(self, owner: str, repo: str) -> SyncStats
        # Pobierz Issues z GitHub
        # Dla każdego Issue: upsert Task (source='github_issue')
        # Mapowanie: open→todo, closed→done

    async def handle_webhook_event(self, event: WebhookEvent, user_id: UUID) -> None
        # Znajdź lub utwórz Task na podstawie event.external_id + repo
        # Zaktualizuj status na podstawie event.action

@dataclass
class SyncStats:
    tasks_created: int
    tasks_updated: int
    errors: int
```

## Szyfrowanie tokenów

Tokeny GitHub przechowywane w kolumnie `access_token_encrypted` (bytes).

```python
from cryptography.fernet import Fernet

# Klucz z konfiguracji: DEVFLOW_API_ENCRYPTION_KEY (base64-encoded 32 bytes)
def encrypt_token(token: str, key: str) -> bytes:
    return Fernet(key).encrypt(token.encode())

def decrypt_token(encrypted: bytes, key: str) -> str:
    return Fernet(key).decrypt(encrypted).decode()
```

Wymagana zależność: `cryptography>=43.0` (dodać do `pyproject.toml`).

## Zmienne środowiskowe

| Zmienna | Opis |
|---|---|
| `DEVFLOW_API_GITHUB_CLIENT_ID` | GitHub OAuth App Client ID |
| `DEVFLOW_API_GITHUB_CLIENT_SECRET` | GitHub OAuth App Client Secret |
| `DEVFLOW_API_GITHUB_REDIRECT_URI` | Callback URL po autoryzacji |
| `DEVFLOW_API_GITHUB_WEBHOOK_SECRET` | Secret do weryfikacji HMAC webhooków |
| `DEVFLOW_API_ENCRYPTION_KEY` | Klucz Fernet do szyfrowania tokenów |
