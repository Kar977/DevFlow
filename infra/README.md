# Infrastructure

Konfiguracja lokalna i deployment DevFlow Insight.

## Stack

- **API:** FastAPI na porcie `8000`
- **Baza danych:** PostgreSQL 18.3 na porcie `5432`
- **Cache** *(do dodania)*: Redis na porcie `6379` — potrzebny dla cachowania metryk

## Uruchomienie lokalne

### Wymagania

- Docker Desktop
- Plik `apps/api/.env` (skopiuj z `.env.example` i uzupełnij)

### Pierwsze uruchomienie

```powershell
# Skopiuj konfigurację
cp apps/api/.env.example apps/api/.env

# Uruchom stack (API + PostgreSQL)
docker compose -f infra/docker-compose.yml up -d

# Uruchom migracje bazy danych
docker compose -f infra/docker-compose.yml exec api uv run alembic upgrade head

# Zweryfikuj działanie
curl http://localhost:8000/health
# Oczekiwana odpowiedź: {"status": "ok", "environment": "local"}
```

### Kolejne uruchomienia

```powershell
docker compose -f infra/docker-compose.yml up -d
```

### Zatrzymanie

```powershell
docker compose -f infra/docker-compose.yml down
# Z usunięciem danych bazy:
docker compose -f infra/docker-compose.yml down -v
```

## Zmienne środowiskowe

Plik `apps/api/.env`:

| Zmienna | Wartość lokalna | Opis |
|---|---|---|
| `DEVFLOW_API_ENVIRONMENT` | `local` | Środowisko: local/test/staging/production |
| `DEVFLOW_API_DEBUG` | `true` | Tryb debug |
| `DEVFLOW_API_DATABASE_URL` | `postgresql+asyncpg://devflow:devflow@localhost:5432/devflow` | URL bazy |
| `DEVFLOW_API_CORS_ORIGINS` | `["http://localhost:3000","http://localhost:5173"]` | Dozwolone origins |
| `DEVFLOW_API_SECRET_KEY` | *wygeneruj losowy string 32+ znaków* | Klucz podpisywania JWT |
| `DEVFLOW_API_GITHUB_CLIENT_ID` | *z GitHub OAuth App* | GitHub OAuth Client ID |
| `DEVFLOW_API_GITHUB_CLIENT_SECRET` | *z GitHub OAuth App* | GitHub OAuth Client Secret |
| `DEVFLOW_API_GITHUB_WEBHOOK_SECRET` | *wygeneruj losowy string* | GitHub webhook HMAC secret |

**Uwaga:** `DEVFLOW_API_SECRET_KEY`, `DEVFLOW_API_GITHUB_CLIENT_SECRET` i `DEVFLOW_API_GITHUB_WEBHOOK_SECRET` nigdy nie trafiają do repozytorium.

## Docker Compose — services

### Aktualny stan

```yaml
services:
  api:       # FastAPI na porcie 8000
  postgres:  # PostgreSQL 18.3 na porcie 5432
```

### Do dodania: Redis (cache metryk)

Serwis Redis powinien zostać dodany do `docker-compose.yml` gdy zaimplementowany zostanie `MetricsService` z cachowaniem:

```yaml
  redis:
    image: redis:7-alpine
    ports:
      - "6379:6379"
    volumes:
      - devflow-redis-data:/data
```

## Migracje bazy danych

```powershell
# Utwórz nową migrację (po dodaniu modeli ORM)
docker compose -f infra/docker-compose.yml exec api uv run alembic revision --autogenerate -m "add users table"

# Zastosuj migracje
docker compose -f infra/docker-compose.yml exec api uv run alembic upgrade head

# Cofnij ostatnią migrację
docker compose -f infra/docker-compose.yml exec api uv run alembic downgrade -1

# Sprawdź historię migracji
docker compose -f infra/docker-compose.yml exec api uv run alembic history
```

## CI/CD (do zaimplementowania)

Należy stworzyć następujące GitHub Actions workflows w `.github/workflows/`:

### `ci.yml` — weryfikacja każdego PR

Wyzwolenie: każdy push do branch + otworzenie/aktualizacja PR

Kroki:
1. Checkout kodu
2. Setup Python 3.14 + uv
3. `uv sync` — instalacja zależności
4. `uv run ruff format --check .` — sprawdzenie formatowania
5. `uv run ruff check .` — linting
6. `uv run mypy src tests` — type checking
7. Uruchomienie PostgreSQL (service container)
8. `uv run pytest` — testy integracyjne

### `docker.yml` — build obrazu

Wyzwolenie: push do `main`

Kroki:
1. Build obrazu Docker
2. Push do GitHub Container Registry (`ghcr.io`)
3. Tagowanie: `latest` + SHA commita

### `release.yml` — wersjonowanie

Wyzwolenie: utworzenie tagu `v*.*.*`

Kroki:
1. Build obrazu z tagiem wersji
2. Stworzenie GitHub Release z changelogiem

## Deployment produkcyjny (planowany)

Na produkcji każdy serwis powinien być osobnym kontenerem/poddem:
- **API:** skalowalne poziomo (min. 2 repliki), bez stanu
- **PostgreSQL:** zarządzana instancja (np. AWS RDS, Supabase)
- **Redis:** zarządzana instancja (np. AWS ElastiCache)
- **Secrets:** AWS Secrets Manager lub HashiCorp Vault (nie zmienne środowiskowe)
