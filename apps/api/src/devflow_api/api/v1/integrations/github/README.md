# GitHub Integration Routes

Opcjonalna integracja z GitHub — autoryzacja OAuth, synchronizacja danych i obsługa webhooków.

Integracja GitHub jest **niezależna od core funkcjonalności** (tasks, projects, metrics działają bez niej).
Po połączeniu GitHub, PR i Issues są automatycznie synchronizowane jako taski w DevFlow.

## Endpointy do zaimplementowania

### `POST /api/v1/integrations/github/authorize`

Inicjuj GitHub OAuth flow. Zwraca URL do którego należy przekierować użytkownika.

Response `200 OK`:
```json
{
  "authorization_url": "https://github.com/login/oauth/authorize?client_id=...&state=...&scope=repo%2Cread%3Auser"
}
```

`state` = losowy token CSRF, przechowywany tymczasowo (w cache lub session) do weryfikacji w callback.

---

### `GET /api/v1/integrations/github/callback`

Callback GitHub OAuth — wywoływany przez GitHub po autoryzacji usera.
Ten endpoint **nie jest chroniony** JWT — GitHub wywołuje go bezpośrednio.

Query params (z GitHub):
- `code` — jednorazowy authorization code
- `state` — token CSRF do weryfikacji

Logika:
1. Zweryfikuj `state` (CSRF protection)
2. Wymień `code` na `access_token` (przez `GitHubOAuthClient`)
3. Pobierz profil GitHub usera
4. Zaszyfruj token, zapisz `GitHubConnection` w bazie
5. Przekieruj do frontendu: `302 → /integrations/github/success`

Response: `302 Redirect` (lub `200 OK` z danymi jeśli frontend SPA obsługuje callback).

---

### `GET /api/v1/integrations/github/status`

Status połączenia GitHub dla zalogowanego użytkownika.

Response `200 OK` gdy połączony:
```json
{
  "connected": true,
  "github_username": "jankowalski",
  "scopes": ["repo", "read:user", "read:org"],
  "connected_at": "2025-01-15T10:00:00Z",
  "last_sync_at": "2025-01-27T08:30:00Z"
}
```

Response gdy niepołączony:
```json
{
  "connected": false
}
```

---

### `DELETE /api/v1/integrations/github/disconnect`

Odłącz GitHub — usuwa `GitHubConnection` z bazy.
Taski zaimportowane z GitHub (source=`github_pr`/`github_issue`) **pozostają** w systemie.

Response `204 No Content`.

---

### `POST /api/v1/integrations/github/sync`

Ręczne wyzwolenie synchronizacji.

Request (opcjonalnie):
```json
{
  "repo_full_name": "owner/repo"
}
```

Jeśli `repo_full_name` nie podane: synchronizuj wszystkie repozytoria usera.

Response `200 OK`:
```json
{
  "tasks_created": 12,
  "tasks_updated": 5,
  "synced_at": "2025-01-27T10:05:00Z"
}
```

Synchronizacja działa asynchronicznie jako background task jeśli wiele repozytoriów.

---

### `POST /api/v1/integrations/github/webhooks`

Receiver webhooków od GitHub.

**Ten endpoint nie jest chroniony JWT** — przyjmuje requesty od GitHub.
Autoryzacja przez weryfikację HMAC-SHA256 signature z headera `X-Hub-Signature-256`.

Headers wymagane przez GitHub:
- `X-GitHub-Event` — typ eventu: `pull_request`, `issues`, `ping`
- `X-Hub-Signature-256` — `sha256=<HMAC>` (weryfikowany przez `webhooks.verify_signature`)

Obsługiwane eventy:

| Event | Action | Efekt |
|---|---|---|
| `pull_request` | `opened` | Utwórz Task z `source=github_pr`, `status=in_progress` |
| `pull_request` | `closed` + merged=true | Zaktualizuj Task → `status=done` |
| `pull_request` | `closed` + merged=false | Zaktualizuj Task → `status=cancelled` |
| `pull_request` | `reopened` | Zaktualizuj Task → `status=in_progress` |
| `issues` | `opened` | Utwórz Task z `source=github_issue`, `status=todo` |
| `issues` | `closed` | Zaktualizuj Task → `status=done` |
| `issues` | `reopened` | Zaktualizuj Task → `status=todo` |
| `ping` | — | Odpowiedz `200 OK` (handshake przy konfiguracji webhooka) |

Response `200 OK`:
```json
{ "received": true }
```

Błąd: `401 Unauthorized` gdy signature nieprawidłowy.
Nieobsługiwane eventy: zignoruj, zwróć `200 OK`.

---

## Konfiguracja webhooka w GitHub

Aby otrzymywać webhooki, należy skonfigurować webhook w repozytorium lub organizacji GitHub:

1. Przejdź do `Settings → Webhooks → Add webhook`
2. **Payload URL:** `https://api.devflow.example.com/api/v1/integrations/github/webhooks`
3. **Content type:** `application/json`
4. **Secret:** wartość z `DEVFLOW_API_GITHUB_WEBHOOK_SECRET`
5. **Events:** `Pull requests`, `Issues`

---

## Pliki do stworzenia

- `routes.py` — route handlery (zastąpić obecny placeholder)
- `../../../core/integrations/github/client.py` — `GitHubClient`
- `../../../core/integrations/github/oauth.py` — `GitHubOAuthClient`
- `../../../core/integrations/github/webhooks.py` — `verify_signature`, `parse_event`
- `../../../core/integrations/github/sync.py` — `GitHubSyncRunner`
- `../../../core/schemas/github/` — `GitHubConnectionResponse`, `AuthorizeResponse`, `SyncResultResponse`
- `../../../core/services/github_sync.py` — `GitHubSyncService`
- `../../../core/repositories/github_connection.py` — `GitHubConnectionRepository`
- `../../../core/models/github_connection.py` — model `GitHubConnection`
- Migracja Alembic: tabela `github_connections`

## Zależności do dodania (`pyproject.toml`)

```toml
cryptography = ">=43.0"   # Fernet do szyfrowania tokenów
httpx = ">=0.28"           # już jest — async client dla GitHub API
```
