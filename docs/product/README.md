# DevFlow Insight — Wymagania produktowe

## Wizja produktu

DevFlow Insight daje developerowi jedno miejsce do zarządzania pracą i rozumienia własnej produktywności. Zamiast zgadywać "czy jestem efektywny?", developer widzi dane: ile tasków zamknął, jak dokładnie estymuje, w jakich godzinach jest najbardziej skupiony.

**Problem który rozwiązujemy:** Developerzy nie mają narzędzia które jednocześnie pozwala zarządzać pracą i mierzyć produktywność w sposób osobisty i kontekstowy — bez narzutu PMowego.

## Użytkownicy

### Główny użytkownik: Developer

Programista pracujący indywidualnie lub w małym zespole (2–15 osób). Chce:
- Wiedzieć nad czym pracuje i co ma zrobić dalej
- Nie tracić czasu na narzędzia do zarządzania projektem
- Rozumieć swoje tempo pracy i obszary do poprawy
- Opcjonalnie: połączyć z GitHub żeby nie duplikować danych

### Drugorzędny użytkownik: Tech Lead / Engineering Manager

Chce widzieć agregaty dla zespołu: velocity, rozkład pracy, kto jest przeciążony. Nie wnika w szczegóły tasków indywidualnych developerów.

---

## User Stories

### Auth

- Jako developer chcę się zarejestrować emailem i hasłem, żeby mieć prywatne konto
- Jako developer chcę się zalogować i otrzymać JWT token, żeby korzystać z API
- Jako developer chcę odświeżyć token bez ponownego logowania, żeby sesja nie wygasała niespodziewanie
- Jako developer chcę wylogować się i unieważnić token, żeby sesja była bezpieczna
- Jako developer chcę zaktualizować swoje dane profilowe (imię, avatar URL)

### Organizations (Workspaces/Teamy)

- Jako developer chcę stworzyć workspace/organizację, żeby grupować projekty
- Jako developer chcę zaprosić innych developerów do organizacji, żeby pracować zespołowo
- Jako tech lead chcę nadawać role (owner/admin/member), żeby kontrolować uprawnienia
- Jako developer chcę należeć do wielu organizacji (np. praca + side projects)

### Projects

- Jako developer chcę tworzyć projekty w ramach organizacji lub osobiste
- Jako developer chcę opisać projekt (nazwa, opis, status: active/archived)
- Jako developer chcę opcjonalnie przypisać projekt do repozytorium GitHub
- Jako developer chcę widzieć statystyki projektu: ile tasków, ile otwartych, ile przeterminowanych

### Tasks + Time Tracking

- Jako developer chcę tworzyć taski z tytułem, opisem, priorytetem i estymacją czasu
- Jako developer chcę zmieniać status taska: backlog → todo → in_progress → review → done
- Jako developer chcę uruchomić timer przy starcie pracy nad taskiem
- Jako developer chcę zatrzymać timer kiedy kończę pracę lub przerywam
- Jako developer chcę widzieć historię sesji pracy na tasku
- Jako developer chcę widzieć łączny czas spędzony na tasku vs estymację
- Jako developer chcę mieć taski importowane z GitHub PR/issues (jeśli GitHub połączony)

### Metryki i Dashboardy

- Jako developer chcę widzieć summary mojej produktywności za ostatnie 7/30 dni
- Jako developer chcę widzieć velocity: ile tasków zamykam tygodniowo, z trendem
- Jako developer chcę widzieć mój czas aktywnej pracy dziennie (z time tracking)
- Jako developer chcę widzieć estimation accuracy: jak dokładnie szacuję taski
- Jako developer chcę widzieć streaka aktywności: ile dni z rzędu zamknąłem przynajmniej 1 task
- Jako developer chcę widzieć project health: % tasków overdue per projekt
- Jako tech lead chcę widzieć metryki agregowane dla całej organizacji

### Reports

- Jako developer chcę wygenerować tygodniowe podsumowanie swojej pracy
- Jako developer chcę eksportować dane do JSON/CSV
- Jako tech lead chcę raporty statusu projektu dla stakeholderów

### GitHub Integration

- Jako developer chcę połączyć konto GitHub przez OAuth
- Jako developer chcę synchronizować PR jako taski (automatycznie przez webhook)
- Jako developer chcę synchronizować Issues jako taski
- Jako developer chcę ręcznie wyzwolić synchronizację
- Jako developer chcę odłączyć GitHub i usunąć dane połączenia

---

## Metryki produktywności

Poniższe metryki oblicza `MetricsService` na podstawie danych z tabel `tasks` i `work_sessions`.

### Velocity

```
velocity = liczba tasków ze statusem 'done' w danym tygodniu
trend = porównanie z poprzednimi 4 tygodniami
```

### Completion Rate

```
completion_rate = done_tasks / (done_tasks + cancelled_tasks + total_open_tasks) * 100
okres: ostatnie 30 dni
```

### Estimation Accuracy

```
accuracy = rzeczywisty_czas_minuty / estymowany_czas_minuty
- ratio < 0.8 → under-used (szacujesz za wysoko)
- ratio 0.8–1.2 → accurate
- ratio > 1.2 → over-run (niedoszacowanie)
liczone tylko dla tasków z `done` i uzupełnioną estymacją
```

### Daily Active Hours

```
active_hours_per_day = sum(work_sessions.duration_minutes) / 60
agregowane dziennie, wyświetlane jako heatmap lub wykres słupkowy
```

### Task Streak

```
streak = max. liczba kolejnych dni w których developer zamknął >= 1 task
current_streak = aktualna seria
longest_streak = rekordowa seria
```

### Project Health

```
overdue_rate = taski z due_date < now() i status != 'done' / total_tasks * 100
status: healthy (<10%), at_risk (10-30%), critical (>30%)
```

---

## Mapowanie funkcjonalności na moduły API

| Funkcjonalność | Router | Ścieżka bazowa |
|---|---|---|
| Auth | auth | `/api/v1/auth` |
| Workspaces/Teams | organizations | `/api/v1/organizations` |
| Projekty | repositories | `/api/v1/projects` |
| Taski + Time Tracking | pull_requests | `/api/v1/tasks` |
| Metryki | metrics | `/api/v1/metrics` |
| Raporty | reports | `/api/v1/reports` |
| GitHub sync | integrations/github | `/api/v1/integrations/github` |

**Uwaga:** Router `pull_requests` obsługuje taski (zmiana roli domeny). Router `repositories` obsługuje projekty. Nazwy routerów w kodzie pozostają niezmienione dla zachowania ciągłości scaffoldu.

---

## Priorytety implementacji (Etap 1 — backend)

Kolejność jest wymuszona zależnościami technicznymi:

1. **Auth** — fundament: bez użytkownika nic innego nie działa
2. **Organizations** — kontener dla projektów
3. **Projects** — kontener dla tasków
4. **Tasks + Time Tracking** — core product value
5. **Metrics** — wymaga danych z tasks/work_sessions
6. **GitHub Integration** — opcjonalna, wymaga działającego task management
7. **Reports** — wymaga danych z metrics/tasks

---

## Wymagania niefunkcjonalne

- **Latency:** endpointy CRUD < 200ms p95, metryki < 500ms p95 (z cache)
- **Auth:** JWT access token TTL 15 minut, refresh token TTL 30 dni
- **Bezpieczeństwo:** hasła hashowane bcrypt (cost factor 12), tokeny GitHub szyfrowane w bazie
- **Paginacja:** wszystkie endpointy listujące obsługują `limit` (max 100) i `offset`
- **Walidacja:** Pydantic v2 na wszystkich inputach; błędy w standardowym formacie `{"error": {...}}`
- **Testy:** każdy serwis i endpoint powinien mieć testy integracyjne
