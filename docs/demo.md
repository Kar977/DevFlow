# Branch `demo` — publiczna, read-only wersja pokazowa

Ten branch jest odbiciem `main`, wdrażanym w dokładnie ten sam sposób (ten sam `Dockerfile`,
ten sam `entrypoint.sh`, ta sama reguła rewrite proxy na Render), różniącym się wyłącznie
addytywną warstwą trybu demo. Celem jest publiczny, w pełni funkcjonalny pokaz aplikacji:
każdy odwiedzający może przeklikać się przez wszystkie zakładki i zobaczyć realistycznie
wyglądające dane, ale nie może niczego zmienić — ani w aplikacji, ani w serwisach z nią
połączonych (GitHub).

## Co dokładnie blokuje tryb demo

Gwarancja żyje w backendzie, nie tylko w interfejsie. Flaga `DEVFLOW_API_DEMO_MODE=true`
włącza `DemoReadOnlyMiddleware` (`apps/api/src/devflow_api/main.py`), które przepuszcza:

- każde żądanie `GET`, `HEAD`, `OPTIONS`,
- dokładnie trzy ścieżki zapisu, po pełnym dopasowaniu ścieżki (nie po prefiksie):
  `POST /api/v1/auth/login`, `POST /api/v1/auth/refresh`, `POST /api/v1/auth/logout`.

Wszystko inne — rejestracja, tworzenie/edycja/usuwanie zadań, projektów, organizacji,
generowanie raportów, synchronizacja z GitHubem, webhooki — dostaje `403` z kodem błędu
`demo_read_only`. Frontend (`apps/web/src/shared/api/client.ts`) ma równoległy interceptor,
który przechwytuje te same żądania po stronie przeglądarki i pokazuje czytelny komunikat —
ale to wygoda, nie zabezpieczenie. Nawet ktoś, kto ominie frontend, nie zapisze niczego.

Drugą, niezależną warstwą ochrony jest brak jakiejkolwiek konfiguracji GitHuba
(`DEVFLOW_API_GITHUB_*` puste na deploymencie demo) — kod fizycznie nie ma czym
uwierzytelnić się do GitHub API, więc nawet teoretyczne obejście blokady zapisu nie
dosięgnęłoby żadnego zewnętrznego serwisu.

## Dane pokazowe

Baza jest czyszczona i zasiewana od nowa przy **każdym starcie kontenera**
(`apps/api/entrypoint.sh` woła `python -m devflow_api.demo` po migracjach, gdy
`DEVFLOW_API_DEMO_MODE=true`). Cały generator żyje w `apps/api/src/devflow_api/demo/`:

- `dataset.py` — czysta, w pełni testowalna bez bazy budowa zbioru: konto demo + 6
  współpracowników w dwóch organizacjach, 5 projektów, ~200-300 zadań z pełną historią
  przejść statusów i sesjami pracy, repozytoria z PR-ami i recenzjami, 5 raportów
  (4 wygenerowane przez prawdziwy `core.services.report._do_generate_report`, jeden ze
  statusem `failed`),
- `timeline.py` — każda data liczona względem `now` w momencie zasiewu, nigdy na sztywno,
- `ids.py` — deterministyczne `uuid5`, więc URL-e w rodzaju `/projects/<id>` przeżywają reseed,
- `wipe.py` — jeden `TRUNCATE ... CASCADE` przed zapisem,
- `runner.py` — orkiestracja: wipe → zapis w jednej transakcji → generowanie raportów.

Zbiór jest tak dobrany, żeby żadna zakładka nie była pusta: konto demo ma bieżącą serię
ukończeń (6 dni) różną od rekordowej (9 dni), projekty pokrywają wszystkie trzy pasma
zdrowia (`healthy`/`at_risk`/`critical`), część PR-ów jest przeterminowana, a przynajmniej
jeden ma recenzję z ostatnich 7 dni (żeby `review_velocity` nie było puste).

**Bezpiecznik:** `python -m devflow_api.demo` odmawia działania, jeśli
`DEVFLOW_API_DEMO_MODE` nie jest ustawione na `true` — nie da się przypadkiem wyczyścić
bazy produkcyjnej tym poleceniem.

## Logowanie

Wszyscy odwiedzający współdzielą jedno konto (`demo@devflow.app`). Ekran logowania w
trybie demo (`apps/web/src/features/auth/components/LoginForm.tsx`) pokazuje przycisk
„Wejdź do demo”, który loguje tym kontem bez wpisywania danych; zwykły formularz zostaje
dostępny pod spodem, a link do rejestracji jest ukryty (rejestracja i tak jest odrzucana
przez API).

## Zmienne środowiskowe specyficzne dla demo

| Zmienna | Wartość | Dlaczego |
|---|---|---|
| `DEVFLOW_API_DEMO_MODE` | `true` | włącza blokadę zapisu i reseed przy starcie |
| `DEVFLOW_API_ACCESS_TOKEN_EXPIRE_MINUTES` | `720` | wydłużony token dostępu — na współdzielonym koncie demo wyścig dwóch odświeżeń tokenu (`AuthService.refresh`) unieważniłby sesje wszystkich innych zwiedzających; przy dłuższym tokenie odświeżenie praktycznie nigdy nie zachodzi |
| `VITE_DEMO_MODE` | `true` | ustawione w `apps/web/.env.production` (wyjątek w `.gitignore`), Vite wczytuje je automatycznie przy `vite build` — front nie wymaga żadnej dodatkowej konfiguracji na hostingu |

Wszystkie zmienne `DEVFLOW_API_GITHUB_*` powinny pozostać puste na deploymencie demo.

## Uruchomienie lokalne

```powershell
# w infra/docker-compose.yml, na czas testu, do serwisu api:
#   DEVFLOW_API_DEMO_MODE: "true"
docker compose -f infra/docker-compose.yml up -d --build
curl http://localhost:8000/health
```

W logach kontenera: `Running database migrations...` → `Seeding demo data...` → wpis z
liczbą zasianych wierszy → `Starting API server...`.

## Aktualizacja z `main`

Diff wobec `main` jest czysto addytywny (nowy pakiet `demo/`, kilka krótkich, warunkowych
wpięć w `main.py`/`config.py`/`entrypoint.sh`/`client.ts`/`router.tsx`/`AppShell.tsx`), więc
`git merge main` powinien przechodzić bez konfliktów. Po merge'u uruchom pełny zestaw
weryfikacji z `apps/api/` (`ruff check .`, `ruff format --check .`, `mypy src tests`,
`pytest`) i z `apps/web/` (`npx tsc -b`, `npm run build`, `npx vitest run`).

## Wdrożenie na Render

Patrz sekcja „Przełączenie usług Render” w planie implementacji tej funkcji — w skrócie:
usługi `devflow-api`/`devflow-web` przełączone na branch `demo`, dodane
`DEVFLOW_API_DEMO_MODE=true` i `DEVFLOW_API_ACCESS_TOKEN_EXPIRE_MINUTES=720`, usunięte
wszystkie zmienne `DEVFLOW_API_GITHUB_*`. Reszta konfiguracji (`PORT`, `DEVFLOW_API_SECRET_KEY`,
`DEVFLOW_API_ALLOWED_HOSTS`, reguły rewrite proxy) bez zmian względem `main`.

**Uwaga:** baza danych jest czyszczona przy każdym starcie kontenera w trybie demo. Jeśli
`devflow-api` na Render zostanie przełączony na branch `demo` bez zmiany
`DEVFLOW_API_DATABASE_URL`, dane w dotychczasowej bazie `devflow-db` zostaną skasowane przy
pierwszym deployu — rozważ osobną instancję bazy dla demo.
