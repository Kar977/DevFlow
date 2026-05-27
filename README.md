# DevFlow Insight

DevFlow Insight to narzędzie produktywności dla developerów. Pozwala zarządzać projektami i taskami, śledzić czas pracy oraz mierzyć własną produktywność przez dashboardy analityczne.

## Czym jest DevFlow Insight?

Developer loguje się i może:
- Tworzyć projekty i organizować pracę w zespołach (organizations)
- Zarządzać taskami: status, priorytet, estymacja czasu
- Śledzić czas pracy na taskach (start/stop timer)
- Przeglądać dashboardy z metrykami: velocity, completion rate, estimation accuracy, streaki aktywności
- Opcjonalnie: połączyć konto GitHub i synchronizować PR/issues jako taski

## Roadmapa

### Etap 1 — Backend API (aktualny etap)

Wyłącznie backend FastAPI z pełnym REST API. Brak frontendu.

Domeny do zaimplementowania (kolejność odzwierciedla zależności):
1. **Auth** — rejestracja, logowanie JWT, zarządzanie tokenami
2. **Organizations** — workspace/team management z rolami
3. **Projects** — projekty developerskie (router: `/repositories`)
4. **Tasks + Time Tracking** — taski z timerem (router: `/pull-requests`)
5. **Metrics** — metryki produktywności i dashboardy
6. **Reports** — eksport danych (JSON → CSV/PDF)
7. **GitHub Integration** — opcjonalna synchronizacja z GitHub

### Etap 2 — Frontend (planowany)

Aplikacja React + TypeScript + Vite w `apps/web/`. Widoki:
- Ekran logowania i rejestracji
- Dashboard z metrykami developera
- Lista projektów i tasków (Kanban/Lista)
- Timer do śledzenia czasu pracy
- Widok raportów i eksportów

## Architektura systemu

```
┌─────────────────────────────────────────────────────┐
│                    KLIENCI (Etap 2)                  │
│         React App (apps/web)  |  Swagger UI          │
└─────────────────┬───────────────────────────────────┘
                  │ HTTP/REST
┌─────────────────▼───────────────────────────────────┐
│              FastAPI Backend (apps/api)               │
│                                                      │
│  /api/v1/auth          /api/v1/organizations         │
│  /api/v1/projects      /api/v1/tasks                 │
│  /api/v1/metrics       /api/v1/reports               │
│  /api/v1/integrations/github                         │
│                                                      │
│  Core: config | database | security | errors         │
│  Layers: routes → services → repositories → models   │
└─────────────────┬───────────────────────────────────┘
                  │
┌─────────────────▼───────────────────────────────────┐
│              PostgreSQL 18.3                          │
│   users | organizations | projects | tasks           │
│   work_sessions | reports | github_connections       │
└─────────────────────────────────────────────────────┘
```

## Layout monorepo

```
devflow/
├── apps/
│   └── api/                # FastAPI backend (Etap 1)
│       ├── src/devflow_api/
│       │   ├── api/v1/     # Route handlers per domain
│       │   └── core/       # Config, DB, models, services
│       ├── tests/
│       ├── migrations/     # Alembic migrations
│       └── README.md       # Pełna spec API
├── docs/
│   └── product/
│       └── README.md       # Wymagania produktowe i user stories
├── infra/
│   ├── docker-compose.yml  # API + PostgreSQL + Redis
│   └── README.md           # Instrukcja infrastruktury
└── README.md               # Ten plik
```

## Szybki start

Wymagania: Docker, Docker Compose.

```powershell
# 1. Skopiuj konfigurację środowiska
cp apps/api/.env.example apps/api/.env

# 2. Uruchom stack
docker compose -f infra/docker-compose.yml up -d

# 3. Uruchom migracje bazy
docker compose -f infra/docker-compose.yml exec api uv run alembic upgrade head

# 4. Sprawdź czy działa
curl http://localhost:8000/health
```

API jest dostępne pod `http://localhost:8000`. Interaktywna dokumentacja Swagger: `http://localhost:8000/docs`.

## Dokumentacja

- [Backend API](apps/api/README.md) — specyfikacja endpointów, modele danych, development guide
- [Wymagania produktowe](docs/product/README.md) — user stories, metryki, wizja
- [Infrastruktura](infra/README.md) — Docker, CI/CD, deployment
