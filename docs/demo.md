# Branch `demo` — publiczna, edytowalna wersja pokazowa

Ten branch jest odbiciem `main`, wdrażanym w dokładnie ten sam sposób (ten sam `Dockerfile`,
ten sam `entrypoint.sh`, ta sama reguła rewrite proxy na Render), różniącym się wyłącznie
addytywną warstwą trybu demo. Celem jest publiczny, w pełni funkcjonalny pokaz aplikacji:
każdy odwiedzający może swobodnie dodawać, edytować i usuwać zadania, projekty, raporty czy
ustawienia organizacji, na dwóch twardych zasadach:

- **integracja z GitHubem jest w pełni symulowana** — nic, co zrobi zwiedzający, nie dotyka
  prawdziwego konta ani repozytorium GitHub;
- **dane wracają do stanu początkowego co jakiś czas** (domyślnie co 30 minut), więc kolejny
  zwiedzający zawsze zastaje demo w sensownym, prezentowalnym stanie.

## Co dokładnie blokuje tryb demo

Gwarancja żyje w backendzie, nie tylko w interfejsie. Flaga `DEVFLOW_API_DEMO_MODE=true`
włącza `DemoGuardMiddleware` (`apps/api/src/devflow_api/main.py`) — pure-ASGI middleware
dopasowujące po dokładnej parze `(metoda, ścieżka)`, nie po prefiksie. Blokuje wyłącznie:

- `POST /api/v1/auth/register` — wszyscy odwiedzający współdzielą jedno konto, rejestracja
  własnego jest jedyną operacją zapisu odrzucaną na poziomie API (`403`, kod błędu
  `demo_read_only`).

Wszystko inne — tworzenie/edycja/usuwanie zadań, projektów, organizacji, raportów,
synchronizacja z GitHubem — **przechodzi normalnie**. Frontend (`apps/web/src/shared/api/client.ts`)
nie ma już żadnego interceptora blokującego zapisy; jedyne, co API odrzuca (rejestrację),
i tak zwraca ten sam standardowy komunikat błędu, który `getErrorMessage()` pokazuje bez zmian.

## Edycja danych i cykliczny reset

Zamiast blokować zapisy, demo je w pełni dopuszcza i regularnie kasuje efekty zwiedzających.
`Settings.demo_reset_interval_minutes` (env `DEVFLOW_API_DEMO_RESET_INTERVAL_MINUTES`,
domyślnie `30`, `0` wyłącza cykliczny reset) steruje pętlą w tle uruchamianą z lifespanu
FastAPI (`main.py`) — `devflow_api.demo.scheduler.run_reset_loop`. Co interwał woła
`demo.runner.run_seed()`, dokładnie tę samą funkcję, którą `entrypoint.sh` woła raz przy
starcie kontenera.

`run_seed()` czyści bazę (`wipe.wipe_all` — `TRUNCATE ... CASCADE`) i zapisuje świeży zbiór w
**jednej** transakcji — to jest istotne, bo pętla działa na żywym, przyjmującym ruch API:
`TRUNCATE` trzyma blokadę `ACCESS EXCLUSIVE` do commitu, więc równoległe zapytania czekają, a
nie widzą pustej bazy. Generowanie raportów demo idzie osobno, dopiero **po** commicie tej
transakcji (bo `_do_generate_report` otwiera własną sesję i widzi tylko zapisane dane).

**Uwaga do wdrożenia:** pętla resetu żyje w pamięci procesu — przy `uvicorn --workers N > 1`
każdy worker uruchomiłby własną, niezależną pętlę (i próbowałby resetować bazę N razy w tym
samym momencie). `entrypoint.sh` startuje dokładnie jeden worker, więc to nieistotne dzisiaj —
ale gdyby liczba workerów kiedyś wzrosła, reset trzeba by przenieść poza proces API (np. cron
w kontenerze, albo `python -m devflow_api.demo` wołany z zewnętrznego harmonogramu).

Zwiedzający może sprawdzić, kiedy nastąpi kolejny reset, przez `GET /api/v1/demo/status`
(zawsze zamontowany, poza demo zwraca `enabled: false`) — z tego korzysta licznik w
`DemoBanner.tsx` widocznym na każdej zakładce aplikacji.

Access token demo ma świadomie wydłużony czas życia (patrz tabela zmiennych niżej), więc reset
bazy — który czyści też `refresh_tokens` — nie wylogowuje zwiedzającego w trakcie sesji.

## Symulacja integracji z GitHubem

Realny klient GitHub API (`core/integrations/github/client.py::GitHubApiClient`) nigdy nie jest
używany w trybie demo. Cała logika żyje w `apps/api/src/devflow_api/demo/github.py`, bez
rozsiewania warunków `if demo_mode` po serwisach produkcyjnych:

- `DemoGitHubApiClient` — atrapa bez sieci, implementująca wszystkie metody realnego klienta z
  deterministycznymi danymi spójnymi z tym, co seeduje `demo/dataset.py` (ta sama instalacja,
  te same repozytoria). Świadome uproszczenie: „synchronizacja” zawsze zgłasza zero nowych
  PR-ów — historyczne PR-y demo i tak trafiają do bazy bezpośrednio przez seeder, nie przez ten
  klient.
- `DemoInstallationTokenProvider` — stałe fikcyjne tokeny, bez mintowania prawdziwego JWT
  (co i tak by się nie udało — `DEVFLOW_API_GITHUB_APP_*` są puste na deploymencie demo).
- `DemoGitHubAppService` / `DemoGitHubSyncService` — nadpisują tylko `get_install_url` /
  `authorize_url` / `handle_callback`, czyli dokładnie te miejsca, które w realnej integracji
  albo budują URL na `github.com`, albo wołają OAuth code-exchange (funkcja w `oauth.py`, która
  sama otwiera `httpx.AsyncClient`, z pominięciem klienta GitHuba). Zamiast tego przekierowują
  zwiedzającego z powrotem na własne strony (`/integrations/github/setup`,
  `/integrations/github/callback`) i kończą „połączenie” lokalnie. Każda inna metoda tych
  serwisów działa bez zmian, bo dostaje wstrzyknięty demo-klient.

Te trzy warianty są wpinane w trzy fabryki `Depends` (`get_github_app_service`,
`get_github_sync_service`, `get_org_sync_service`) w `core/services/`, warunkowo na
`settings.demo_mode`. `GET /integrations/github/status`, listowanie repozytoriów i PR-ów
działają identycznie jak zwykle — to czyste odczyty z własnej bazy.

Frontend (`GitHubIntegrationPage.tsx`) pokazuje w trybie demo jawną notkę, że integracja jest
symulowana — żeby zwiedzający nie pomyślał, że podpina własne konto GitHub.

## Dane pokazowe

Baza jest czyszczona i zasiewana od nowa przy **każdym starcie kontenera**
(`apps/api/entrypoint.sh` woła `python -m devflow_api.demo` po migracjach, gdy
`DEVFLOW_API_DEMO_MODE=true`) — a potem cyklicznie, patrz sekcja wyżej. Cały generator żyje w
`apps/api/src/devflow_api/demo/`:

- `dataset.py` — czysta, w pełni testowalna bez bazy budowa zbioru: konto demo + 6
  współpracowników w dwóch organizacjach, 5 projektów, ~200-300 zadań z pełną historią
  przejść statusów i sesjami pracy, repozytoria z PR-ami i recenzjami, 5 raportów
  (4 wygenerowane przez prawdziwy `core.services.report._do_generate_report`, jeden ze
  statusem `failed`),
- `timeline.py` — każda data liczona względem `now` w momencie zasiewu, nigdy na sztywno,
- `ids.py` — deterministyczne `uuid5`, więc URL-e w rodzaju `/projects/<id>` przeżywają reseed,
- `wipe.py` — `TRUNCATE ... CASCADE`, w tej samej transakcji co zapis (patrz sekcja wyżej),
- `runner.py` — orkiestracja: wipe + zapis w jednej transakcji → generowanie raportów,
- `scheduler.py` — pętla cyklicznego resetu, uruchamiana z lifespanu `main.py`,
- `github.py` — atrapy integracji z GitHubem (patrz sekcja wyżej).

Zbiór jest tak dobrany, żeby żadna zakładka nie była pusta: konto demo ma bieżącą serię
ukończeń (6 dni) różną od rekordowej (9 dni), projekty pokrywają wszystkie trzy pasma
zdrowia (`healthy`/`at_risk`/`critical`), część PR-ów jest przeterminowana, a przynajmniej
jeden ma recenzję z ostatnich 7 dni (żeby `review_velocity` nie było puste).

**Bezpiecznik:** `python -m devflow_api.demo` odmawia działania, jeśli
`DEVFLOW_API_DEMO_MODE` nie jest ustawione na `true` — nie da się przypadkiem wyczyścić
bazy produkcyjnej tym poleceniem.

## Logowanie

Wszyscy odwiedzający współdzielą jedno konto (`demo@devflow.app`) — rejestracja własnego jest
zablokowana (patrz wyżej), więc to jedyny sposób wejścia. Ekran logowania w trybie demo
(`apps/web/src/features/auth/components/LoginForm.tsx`) pokazuje wyłącznie opis demo, przycisk
„Wejdź do demo” (loguje tym kontem bez wpisywania danych) i ostrzeżenie, że backend na darmowym
hostingu bywa usypiany, więc pierwsze wejście może potrwać kilka minut. Zwykły formularz
e-mail/hasło i link do rejestracji nie są renderowane w tym trybie.

## Zmienne środowiskowe specyficzne dla demo

| Zmienna | Wartość | Dlaczego |
|---|---|---|
| `DEVFLOW_API_DEMO_MODE` | `true` | włącza blokadę rejestracji, symulację GitHuba, reseed przy starcie i cykliczny reset |
| `DEVFLOW_API_DEMO_RESET_INTERVAL_MINUTES` | `30` (domyślne, można pominąć) | jak często dane wracają do stanu początkowego; `0` wyłącza cykliczny reset (zostaje tylko reseed przy starcie kontenera) |
| `DEVFLOW_API_ACCESS_TOKEN_EXPIRE_MINUTES` | `720` | wydłużony token dostępu — na współdzielonym koncie demo wyścig dwóch odświeżeń tokenu (`AuthService.refresh`) unieważniłby sesje wszystkich innych zwiedzających; przy dłuższym tokenie odświeżenie praktycznie nigdy nie zachodzi, a cykliczny reset (który czyści `refresh_tokens`) nie wylogowuje w trakcie sesji |
| `VITE_DEMO_MODE` | `true` | ustawione w `apps/web/.env.production` (wyjątek w `.gitignore`), Vite wczytuje je automatycznie przy `vite build` — front nie wymaga żadnej dodatkowej konfiguracji na hostingu |

Wszystkie zmienne `DEVFLOW_API_GITHUB_*` powinny pozostać puste na deploymencie demo — integracja
jest w pełni symulowana (patrz sekcja wyżej), więc te sekrety nie są nigdzie potrzebne, a ich
brak jest dodatkową, niezależną warstwą ochrony przed przypadkowym wyjściem w sieć.

## Uruchomienie lokalne

```powershell
# w infra/docker-compose.yml, na czas testu, do serwisu api:
#   DEVFLOW_API_DEMO_MODE: "true"
docker compose -f infra/docker-compose.yml up -d --build
curl http://localhost:8000/health
```

W logach kontenera: `Running database migrations...` → `Seeding demo data...` → wpis z
liczbą zasianych wierszy → `Starting API server...` → (po `DEVFLOW_API_DEMO_RESET_INTERVAL_MINUTES`)
`Demo reset loop started (every N min)` i cyklicznie `Demo reset complete: {...}`.

## Aktualizacja z `main`

Diff wobec `main` jest czysto addytywny (nowy pakiet `demo/`, kilka krótkich, warunkowych
wpięć w `main.py`/`config.py`/`entrypoint.sh`/`client.ts`/`router.tsx`/`AppShell.tsx`, oraz
warunkowe gałęzie w trzech fabrykach `get_*_service` w `core/services/`), więc `git merge main`
powinien przechodzić bez konfliktów. Po merge'u uruchom pełny zestaw weryfikacji z `apps/api/`
(`ruff check .`, `ruff format --check .`, `mypy src tests`, `pytest`) i z `apps/web/`
(`npx tsc -b`, `npm run build`, `npx vitest run`).

## Wdrożenie na Render

Patrz sekcja „Przełączenie usług Render” w planie implementacji tej funkcji — w skrócie:
usługi `devflow-api`/`devflow-web` przełączone na branch `demo`, dodane
`DEVFLOW_API_DEMO_MODE=true` i `DEVFLOW_API_ACCESS_TOKEN_EXPIRE_MINUTES=720`
(`DEVFLOW_API_DEMO_RESET_INTERVAL_MINUTES` można pominąć — domyślne `30` wystarcza), usunięte
wszystkie zmienne `DEVFLOW_API_GITHUB_*`. Reszta konfiguracji (`PORT`, `DEVFLOW_API_SECRET_KEY`,
`DEVFLOW_API_ALLOWED_HOSTS`, reguły rewrite proxy) bez zmian względem `main`. Upewnij się, że
usługa uruchamia dokładnie jeden proces/worker uvicorna (patrz ostrzeżenie w sekcji „Edycja
danych i cykliczny reset” wyżej) — `entrypoint.sh` już to gwarantuje, o ile nikt nie nadpisał
komendy startowej.

**Uwaga:** baza danych jest czyszczona przy każdym starcie kontenera w trybie demo (i cyklicznie
w trakcie działania). Jeśli `devflow-api` na Render zostanie przełączony na branch `demo` bez
zmiany `DEVFLOW_API_DATABASE_URL`, dane w dotychczasowej bazie `devflow-db` zostaną skasowane
przy pierwszym deployu — rozważ osobną instancję bazy dla demo.
