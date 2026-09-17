/**
 * Public, editable showcase mode.
 *
 * Set at build time via `VITE_DEMO_MODE` (see `.env.production` on the
 * `demo` branch — Vite loads it automatically for `vite build`, so no
 * extra hosting configuration is needed). A visitor can create, edit, and
 * delete data freely — the backend resets everything to its seeded
 * baseline on a timer instead (`GET /demo/status` reports when the next
 * reset happens; see `shared/ui/DemoBanner.tsx`). The one thing the backend
 * still blocks is registration (`DemoGuardMiddleware`, `code: "demo_read_only"`)
 * — every visitor shares the one demo account. The GitHub integration is
 * fully simulated server-side; nothing a visitor does there ever reaches
 * a real GitHub account.
 */
export const IS_DEMO = import.meta.env.VITE_DEMO_MODE === "true";

/** Shared demo account — the only login every visitor uses. */
export const DEMO_CREDENTIALS = {
  email: "demo@devflow.app",
  password: "DevFlowDemo2026!",
};

export const DEMO_INTRO_TITLE = "DevFlow Insight — demo";

export const DEMO_INTRO_MESSAGE =
  "Przykładowe dane, pełen dostęp. Klikaj, dodawaj, kasuj co chcesz — " +
  "co jakiś czas wszystko wraca do stanu początkowego.";

/** Drugi akapit karty logowania — osobna stała, bo renderuje się jako własny <p>. */
export const DEMO_INTRO_GITHUB_NOTE =
  "GitHub jest symulowany, nie łączy się z prawdziwym kontem.";

export const DEMO_BANNER_MESSAGE =
  "Wersja demonstracyjna — dane są przykładowe i można je swobodnie edytować. " +
  "Co jakiś czas wracają do stanu początkowego, a integracja z GitHubem jest symulowana.";

export const DEMO_COLD_START_MESSAGE =
  "Backend usypia na darmowym hostingu — pierwsze wejście może potrwać kilka minut.";

export const DEMO_LOGIN_ERROR_MESSAGE =
  "Nie udało się połączyć z aplikacją — backend prawdopodobnie właśnie się wybudza. " +
  "Odczekaj chwilę i spróbuj ponownie.";
