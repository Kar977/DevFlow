# DevFlow Insight — Decision Log Addendum

**Date:** 2026-06-26  
**Supplements:** `.local_docs/DevFlow Insight/01-decision-log.md`

---

## ADR-001 — Product pivot: GitHub PR analytics → Developer productivity

### Status
**Accepted** (retrospective; pivot completed without formal record)

### Context
The original Implementation Brief v2.0 and Decision Log (`.local_docs/DevFlow Insight/`)
defined DevFlow Insight as a **GitHub-first PR/code-review analytics tool** for engineering
leads. The core domain was `repositories`, `pull_requests`, `pull_request_reviews`,
`sync_runs`, `metric_snapshots`, and 5 KPIs measuring PR flow health.

### Decision
During implementation the product was pivoted to a **developer productivity platform**:
project and task management, work-session time tracking, and task-based productivity
analytics (velocity, completion rate, estimation accuracy, activity streaks). The GitHub
integration was re-scoped from a read-model source of truth to an optional sync source
(GitHub issues/PRs → Tasks).

### What changed

| Aspect | Original brief | Implemented |
|---|---|---|
| Core domain | repositories / pull\_requests / reviews | projects / tasks / work\_sessions |
| GitHub role | primary data source (sync → analytics) | optional task import |
| KPIs | 5 PR-flow metrics | 7 task-based productivity metrics |
| Frontend stack | Next.js 15 App Router | Vite + React Router v6 |
| Tenancy | single active org | multi-org |
| Roles | admin / manager / viewer | owner / admin / member |
| Auth | preferred cookie-based | JWT bearer + refresh token |

### Rationale
*(Post-hoc reconstruction)* — The developer-productivity framing was chosen during
implementation. The exact rationale was not captured at decision time.

### Consequences
- The original `.local_docs/` brief is **superseded** and should be treated as historical
  context only. It is intentionally not modified.
- `PROGRESS.md` and `README.md` reflect the implemented product, not the original brief.
- A full reconciliation of brief vs. implementation is at
  [`docs/reconciliation-report.md`](./reconciliation-report.md).
- Re-pivoting back to GitHub PR analytics would require building the 15 items listed in
  the reconciliation report's "Luki" section — a substantial separate project.

### Original brief files (historical, do not modify)
- `.local_docs/DevFlow Insight/DevFlow Insight - Implementation Brief.md`
- `.local_docs/DevFlow Insight/01-decision-log.md`
- `.local_docs/DevFlow Insight/02-metrics-definition.md`
- `.local_docs/DevFlow Insight/03-api-spec.md`
- `.local_docs/DevFlow Insight/04-data-model.md`
- `.local_docs/DevFlow Insight/05-mvp-backlog.md`
- `.local_docs/DevFlow Insight/06-ux-screen-spec.md`
- `.local_docs/implementation-guide/` (all files)
