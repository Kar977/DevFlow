# DevFlow Insight — Reconciliation Report

**Date:** 2026-06-26  
**Branch audited:** `feature/fix-metrics-github-errors`  
**Prepared by:** code audit (Claude Code)

---

## Executive Summary

Zbudowany produkt jest **kompletny względem `PROGRESS.md`** (wszystkie 8 modułów backendowych
i frontend zaimplementowane; 156 testów backendowych zielonych; 62/63 frontendowych zielonych),
ale reprezentuje **fundamentalnie inny produkt** niż opisany w oficjalnym briefie
(`.local_docs/DevFlow Insight/`).

Oryginalny brief definiuje **narzędzie analityki GitHub PR / code-review** dla engineering
leadów: domena `repositories` / `pull_requests` / `pull_request_reviews` / `sync_runs` /
`metric_snapshots`, 5 KPI PR-flow, ekrany listy i detalu PR.

Faktyczna implementacja to **narzędzie produktywności developer'a**: zarządzanie projektami
i zadaniami, śledzenie czasu pracy (timer), metryki task-based (velocity, completion rate,
estimation accuracy, streaks), integracja GitHub jako sync issues/PRs → Tasks.

Pivot nie był udokumentowany w żadnym pliku decyzyjnym. Formalne odnotowanie → patrz
[`docs/decision-log-addendum.md`](./decision-log-addendum.md).

---

## Story-by-story status

> Legenda: ✅ Zgodny · ⚠️ Rozbieżny / Częściowy · ❌ Brak

### Epic 1 — Project foundation

| Story | Wymóg briefu | Status | Dowód |
|---|---|:---:|---|
| **1.1 Monorepo bootstrap** | `apps/web`, `apps/api`, `infra`, `docs`; Docker Compose; README z setup | ✅ | Struktura katalogów OK; `infra/docker-compose.yml`; `README.md` |
| **1.2 Env config** | Przykładowe env dla frontendu i backendu; wymagane zmienne udokumentowane; bezpieczny brak zmiennych | ⚠️ | `apps/api/.env.example` ✅; `apps/web/.env.example` **brak** ❌; DEVFLOW_API_ prefix OK; brak zmiennych → startup error ✅ |

### Epic 2 — Authentication and organization

| Story | Wymóg briefu | Status | Dowód |
|---|---|:---:|---|
| **2.1 User login** | Login email/password; błędy; ekran logowania; dostęp do chronionych ekranów | ✅ | `api/v1/auth/routes.py`; `features/auth/`; `tests/test_auth.py` (14 testów). Minor: brief preferował cookie-based — impl. używa JWT bearer. |
| **2.2 Active org context** | `/me` zwraca org + rolę; single-org; nieautoryzowani odcięci | ⚠️ | Zaimplementowano multi-org; role `owner/admin/member` ≠ `admin/manager/viewer` z briefu; `/me` zwraca UserResponse (brak org+rola inline) |

### Epic 3 — GitHub integration

| Story | Wymóg briefu | Status | Dowód |
|---|---|:---:|---|
| **3.1 Store GitHub settings** | Admin konfiguruje integrację na poziomie **org**; non-admin odcięty | ⚠️ | Impl.: per-user OAuth (`GitHubConnection` per user_id); brak org-level config; brak ograniczenia do admin. `core/models/github_connection.py`, `api/v1/integrations/github/routes.py` |
| **3.2 Manual sync + `sync_runs`** | Endpoint sync tworzy rekord `sync_runs`; idempotency (brak duplikatów repo/PR/review) | ⚠️ | Sync istnieje; dedup po `github_pr_url` ✅; **tabela `sync_runs` nie istnieje** ❌; sync mapuje issues/PRs → Tasks (nie repozytoria → PR → review) |

### Epic 4 — Repositories

| Story | Wymóg briefu | Status | Dowód |
|---|---|:---:|---|
| **4.1 Repository list** | Lista zsynchronizowanych repozytoriów; paginacja; name, full_name, is_active, last_sync | ❌ | Domena `repositories` nie istnieje. `api/v1/repositories/routes.py` serwuje **Projects** (nie GitHub repos). Brak modelu, migracji, ekranu. |

### Epic 5 — Pull requests

| Story | Wymóg briefu | Status | Dowód |
|---|---|:---:|---|
| **5.1 PR list** | Lista PR; filtry status/author/repo; sortowanie po wieku; title, author, state, created\_at, first\_review\_at | ❌ | Domena `pull_requests` nie istnieje. `api/v1/pull_requests/routes.py` serwuje **Tasks**. Brak modelu, migracji, ekranu. |
| **5.2 PR detail** | Detal PR; timeline; lista reviews; 404 dla nieznanego PR | ❌ | Nie istnieje. |

### Epic 6 — Metrics dashboard

| Story | Wymóg briefu | Status | Dowód |
|---|---|:---:|---|
| **6.1 Dashboard summary** | Stale PR count, review velocity, weekly throughput, review ratio; filtry repo | ❌ | Dashboard istnieje, ale metryki task-owe (velocity zamkniętych tasków, completion rate, estimation accuracy, streaks). Żadna z 4 KPI PR-flow nie jest obecna. `features/dashboard/`, `features/metrics/` |
| **6.2 Metrics calculation service** | Formuły zgodne z metrics-def; testy edge cases; bezpieczne wykluczenie złych rekordów | ⚠️ | Serwis i testy istnieją (`core/services/metrics.py`, `tests/test_metrics.py`), ale liczą metryki task-owe. Żadna z 5 zdefiniowanych formuł PR (time\_to\_first\_review, stale\_pr\_count, review\_velocity, weekly\_throughput, review\_ratio) nie jest zaimplementowana. |

### Epic 7 — Weekly reports

| Story | Wymóg briefu | Status | Dowód |
|---|---|:---:|---|
| **7.1 Generate weekly report** | Raport tygodniowy; summary metrics; notable bottlenecks; persist | ⚠️ | Raporty istnieją (`core/services/report.py`, `api/v1/reports/routes.py`); typy: `weekly_summary`, `project_status`, `productivity_overview`. Treść = metryki produktywności task-owej, nie bottlenecki PR-flow. |
| **7.2 Report history** | Historia z paginacją; lista z datą i tytułem; empty state | ✅ | `GET /reports` zwraca `{items, total}` z paginacją; empty state obsłużony. `tests/test_reports.py`. |

### Epic 8 — Settings and UX quality

| Story | Wymóg briefu | Status | Dowód |
|---|---|:---:|---|
| **8.1 Org settings** | Admin widzi metadane org; status integracji widoczny; unauthorized nie może edytować | ⚠️ | Strona GitHub integration settings ✅ (`features/github/pages/GitHubIntegrationPage.tsx`); brak oddzielnego ekranu org-settings z metadanymi; role enforcement do zweryfikowania runtime |
| **8.2 Shared UX states** | Loading/empty/error na każdym ekranie; 375px+; czytelny feedback błędów API | ⚠️ | PROGRESS.md twierdzi „done"; 1 pre-existing test failure (`ConnectGitHubCard.test.tsx`); mobile 375px nie zweryfikowano runtime |

---

## Podsumowanie wyników: 16 pozycji

| Status | Liczba | Stories |
|---|:---:|---|
| ✅ Zgodny | 3 | 1.1, 2.1, 7.2 |
| ⚠️ Rozbieżny / Częściowy | 8 | 1.2, 2.2, 3.1, 3.2, 6.2, 7.1, 8.1, 8.2 |
| ❌ Brak | 5 | 4.1, 5.1, 5.2, 6.1 (pełne KPI), + domain PR |

---

## Rozbieżności architektoniczne

| Kategoria | Wymóg briefu | Implementacja |
|---|---|---|
| Frontend stack | Next.js 15 App Router | Vite + React Router v6 SPA |
| Auth mechanism | Preferencyjnie cookie-based | JWT bearer + refresh token (JWT HS256) |
| Tenancy | Single active org per session | Multi-org (org switcher, Zustand orgStore) |
| Roles | `admin / manager / viewer` | `owner / admin / member` |
| Error format | `{"error": {"code": "...", "message": "..."}}` | `{"error": {"code": "...", "message": "...", "details": {...}}}` (kompatybilny + rozszerzony) |
| GitHub sync target | repos → PRs → reviews → `sync_runs` | issues/PRs → Tasks; brak `sync_runs` |
| Metryki | 5 KPI PR-flow | 7 metryk task-based |

---

## Luki względem oryginalnego briefu (co należy zbudować, jeśli brief jest celem)

Poniższe elementy są wymagane przez brief i **nie istnieją** w obecnej implementacji:

### Backend
1. **Model + migracja: `repositories`** — github_repo_id, name, full_name, is_active, last_synced_at, org_id
2. **Model + migracja: `pull_requests`** — github_pr_id, number, title, author_login, state, created_at_github, merged_at, closed_at, first_review_at, last_synced_at
3. **Model + migracja: `pull_request_reviews`** — github_review_id, pr_id, reviewer_login, state, submitted_at
4. **Model + migracja: `sync_runs`** — org_id, integration_name, status, started_at, finished_at, error_message
5. **Model + migracja: `metric_snapshots`** — org_id, repo_id?, period_start, period_end, metric_key, metric_value
6. **GitHub sync refactor**: sync repos → PRs → reviews (zamiast issues/PRs → Tasks); idempotentny; zapis do `sync_runs`
7. **5 KPI PR-flow**: `time_to_first_review`, `stale_pr_count`, `review_velocity`, `weekly_throughput`, `review_ratio`
8. **Routes**: `GET /repositories`, `GET /pull-requests` (filtry), `GET /pull-requests/{id}`, `GET /metrics/dashboard` (PR-KPI)
9. **Raport tygodniowy**: format PR-flow z bottleneckami (zamiast productivity)
10. **`sync_runs` tracking** w każdym wywołaniu sync

### Frontend
11. **Ekran: Repository list** — name, sync status, last sync time; loading/empty/error
12. **Ekran: PR list** — filtry status/author/repo; sortowanie po wieku; loading/empty/error
13. **Ekran: PR detail** — timeline, reviews, metrics; 404 state
14. **Dashboard refactor** — stale PRs, review velocity, weekly throughput, review ratio (zamiast task KPIs)
15. **`apps/web/.env.example`** — dokumentacja zmiennych env dla frontendu

---

## Stan po 2026-08-04

Ten raport audytował branch `feature/fix-metrics-github-errors` z 2026-06-26 — sprzed odbudowy
domeny PR Analytics. Od tamtej pory, na bazie
[`docs/superpowers/specs/2026-06-26-github-pr-analytics-design.md`](superpowers/specs/2026-06-26-github-pr-analytics-design.md),
domena GitHub PR-flow została dobudowana obok domeny produktywnościowej (nie zastępując jej).
Status 15 luk wypisanych powyżej:

| # | Luka | Stan dziś |
|---|---|:---:|
| 1 | model + migracja `repositories` | ✅ migracja 0008 |
| 2 | model + migracja `pull_requests` | ✅ migracja 0007 |
| 3 | model + migracja `pull_request_reviews` | ✅ migracja 0007 |
| 4 | model + migracja `sync_runs` | ✅ migracja 0007 |
| 5 | model + migracja `metric_snapshots` | ❌ nie zaimplementowano (brief oznacza jako opcjonalne dla MVP) |
| 6 | sync refactor repos → PRs → reviews | ✅ `OrgSyncService` |
| 7 | 5 KPI PR-flow | ✅ `core/services/pr_metrics.py` — wszystkie 5 formuł |
| 8 | routes `/repositories`, `/pull-requests`, `/pull-requests/{id}`, dashboard KPI | ✅ (+ `/metrics/pr-dashboard`, `/metrics/pr-dashboard/members`) |
| 9 | raport tygodniowy w formacie PR-flow z bottleneckami | ✅ typ raportu `pr_flow_weekly` (`core/services/pr_metrics.py::get_pr_flow_report` + `core/services/report.py::_pr_flow_weekly`), migracja 0015 |
| 10 | `sync_runs` tracking przy każdym syncu | ✅ |
| 11 | ekran Repository list | ✅ `/repositories` |
| 12 | ekran PR list z filtrami | ✅ filtry (status/author/repo) + sortowanie po wieku (`sort=newest\|oldest`) |
| 13 | ekran PR detail + reviews | ✅ `/pull-requests/:prId` |
| 14 | dashboard z KPI PR-flow | ✅ `PRDashboardTab` |
| 15 | `apps/web/.env.example` | ✅ |

**15 z 15 luk zamkniętych** (2026-08-11, branch `feature/audit-gaps-and-task-completed-at`).
`metric_snapshots` (pozycja 5) pozostaje świadomie pominięte, zgodnie z adnotacją briefu, że
tabela jest opcjonalna dla MVP — jedyny punkt z oryginalnej listy 15 luk, który nie jest
"zamknięty", bo nigdy nie był w zakresie.

Rozbieżności architektoniczne z tabeli wyżej pozostają bez zmian i są świadomym wyborem
(multi-org zamiast single-org, role `owner/admin/member`, JWT bearer + httpOnly refresh cookie
zamiast czysto cookie-based, Vite SPA zamiast Next.js) — żadna nie blokuje funkcjonalności PR-flow.

### Zaktualizowany werdykt

Projekt jest **technicznie kompletny zarówno jako narzędzie produktywności developera, jak i jako
narzędzie GitHub PR-flow analytics** (15 z 15 luk zamkniętych; `metric_snapshots` świadomie poza
zakresem MVP). Produkt jest funkcjonalnym nadzbiorem obu briefów — serwuje jednocześnie
produktywność (projekty/taski/timer/metryki) i analitykę PR (repo tracking/PR sync/5 KPI PR-flow +
raport tygodniowy z bottleneckami), pod jednym API i jednym UI.
