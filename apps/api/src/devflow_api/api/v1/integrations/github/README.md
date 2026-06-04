# GitHub Integration Routes

Optional GitHub integration — OAuth authorization, data synchronization, and webhook handling.

GitHub integration is **independent of core functionality** (tasks, projects, and metrics work without it).
Once connected, GitHub PRs and Issues are automatically synchronized as DevFlow tasks.

## Endpoints to Implement

### `POST /api/v1/integrations/github/authorize`

Start the GitHub OAuth flow. Returns a URL to redirect the user to.

Response `200 OK`:
```json
{
  "authorization_url": "https://github.com/login/oauth/authorize?client_id=...&state=...&scope=repo%2Cread%3Auser"
}
```

`state` = random CSRF token, stored temporarily (in cache or session) for verification in the callback.

---

### `GET /api/v1/integrations/github/callback`

GitHub OAuth callback — called by GitHub after the user authorizes.
This endpoint is **not protected by JWT** — GitHub calls it directly.

Query params (from GitHub):
- `code` — one-time authorization code
- `state` — CSRF token for verification

Logic:
1. Verify `state` (CSRF protection)
2. Exchange `code` for `access_token` (via `GitHubOAuthClient`)
3. Fetch GitHub user profile
4. Encrypt token, save `GitHubConnection` to DB
5. Redirect to frontend: `302 → /integrations/github/success`

Response: `302 Redirect` (or `200 OK` with data if the frontend SPA handles the callback).

---

### `GET /api/v1/integrations/github/status`

GitHub connection status for the authenticated user.

Response `200 OK` when connected:
```json
{
  "connected": true,
  "github_username": "janedoe",
  "scopes": ["repo", "read:user", "read:org"],
  "connected_at": "2025-01-15T10:00:00Z",
  "last_sync_at": "2025-01-27T08:30:00Z"
}
```

Response when not connected:
```json
{
  "connected": false
}
```

---

### `DELETE /api/v1/integrations/github/disconnect`

Disconnect GitHub — removes `GitHubConnection` from the DB.
Tasks imported from GitHub (source=`github_pr`/`github_issue`) **remain** in the system.

Response `204 No Content`.

---

### `POST /api/v1/integrations/github/sync`

Manually trigger synchronization.

Request (optional):
```json
{
  "repo_full_name": "owner/repo"
}
```

If `repo_full_name` is not provided: sync all user repositories.

Response `200 OK`:
```json
{
  "tasks_created": 12,
  "tasks_updated": 5,
  "synced_at": "2025-01-27T10:05:00Z"
}
```

Synchronization runs as a background task when multiple repositories are involved.

---

### `POST /api/v1/integrations/github/webhooks`

GitHub webhook receiver.

**This endpoint is not protected by JWT** — it receives requests from GitHub.
Authorization is via HMAC-SHA256 signature verification from the `X-Hub-Signature-256` header.

Headers required by GitHub:
- `X-GitHub-Event` — event type: `pull_request`, `issues`, `ping`
- `X-Hub-Signature-256` — `sha256=<HMAC>` (verified by `webhooks.verify_signature`)

Handled events:

| Event | Action | Effect |
|---|---|---|
| `pull_request` | `opened` | Create Task with `source=github_pr`, `status=in_progress` |
| `pull_request` | `closed` + merged=true | Update Task → `status=done` |
| `pull_request` | `closed` + merged=false | Update Task → `status=cancelled` |
| `pull_request` | `reopened` | Update Task → `status=in_progress` |
| `issues` | `opened` | Create Task with `source=github_issue`, `status=todo` |
| `issues` | `closed` | Update Task → `status=done` |
| `issues` | `reopened` | Update Task → `status=todo` |
| `ping` | — | Respond `200 OK` (handshake on webhook setup) |

Response `200 OK`:
```json
{ "received": true }
```

Error: `401 Unauthorized` when signature is invalid.
Unsupported events: ignore, return `200 OK`.

---

## Configuring the Webhook in GitHub

To receive webhooks, configure a webhook in the repository or organization settings:

1. Go to `Settings → Webhooks → Add webhook`
2. **Payload URL:** `https://api.devflow.example.com/api/v1/integrations/github/webhooks`
3. **Content type:** `application/json`
4. **Secret:** value from `DEVFLOW_API_GITHUB_WEBHOOK_SECRET`
5. **Events:** `Pull requests`, `Issues`

---

## Files to Create

- `routes.py` — route handlers (replace current placeholder)
- `../../../core/integrations/github/client.py` — `GitHubClient`
- `../../../core/integrations/github/oauth.py` — `GitHubOAuthClient`
- `../../../core/integrations/github/webhooks.py` — `verify_signature`, `parse_event`
- `../../../core/integrations/github/sync.py` — `GitHubSyncRunner`
- `../../../core/schemas/github/` — `GitHubConnectionResponse`, `AuthorizeResponse`, `SyncResultResponse`
- `../../../core/services/github_sync.py` — `GitHubSyncService`
- `../../../core/repositories/github_connection.py` — `GitHubConnectionRepository`
- `../../../core/models/github_connection.py` — `GitHubConnection` model
- Alembic migration: `github_connections` table

## Dependencies to Add (`pyproject.toml`)

```toml
cryptography = ">=43.0"   # Fernet for token encryption
httpx = ">=0.28"           # already present — async client for GitHub API
```
