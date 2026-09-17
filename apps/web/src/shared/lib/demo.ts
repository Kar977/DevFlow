/**
 * Read-only public showcase mode.
 *
 * Set at build time via `VITE_DEMO_MODE` (see `.env.production` on the
 * `demo` branch — Vite loads it automatically for `vite build`, so no
 * extra hosting configuration is needed). The real write guarantee lives
 * in the backend's `DemoReadOnlyMiddleware`; everything here is purely for
 * a clear visitor experience — a synthetic 403 from the API interceptor
 * (see `shared/api/client.ts`) reads identically to a real one either way.
 */
export const IS_DEMO = import.meta.env.VITE_DEMO_MODE === "true";

/** Shared demo account — the only login every visitor uses. */
export const DEMO_CREDENTIALS = {
  email: "demo@devflow.app",
  password: "DevFlowDemo2026!",
};

export const DEMO_INTRO_TITLE = "DevFlow Insight — wersja demonstracyjna";

export const DEMO_INTRO_MESSAGE =
  "To jest wersja demonstracyjna aplikacji, wypełniona przykładowymi danymi. " +
  "Aktywne są wyłącznie operacje odczytu — możesz przeglądać wszystkie zakładki, " +
  "wykresy i zestawienia. Dodawanie, modyfikowanie i usuwanie danych jest " +
  "wyłączone, więc niczego tu nie zepsujesz.";

export const DEMO_BANNER_MESSAGE =
  "Wersja demonstracyjna — dane są przykładowe. Aktywny jest tylko odczyt; " +
  "dodawanie, modyfikowanie i usuwanie danych jest wyłączone.";

export const DEMO_READ_ONLY_TOAST_MESSAGE =
  "Tryb demo — dodawanie, zmiana i usuwanie danych jest wyłączone.";

export const DEMO_COLD_START_MESSAGE =
  "Demo działa na darmowym hostingu — po dłuższej bezczynności backend jest usypiany " +
  "i pierwsze wejście może potrwać kilka minut. Jeśli się nie powiedzie, odczekaj chwilę " +
  "i kliknij ponownie.";

export const DEMO_LOGIN_ERROR_MESSAGE =
  "Nie udało się połączyć z aplikacją — backend prawdopodobnie właśnie się wybudza. " +
  "Odczekaj chwilę i spróbuj ponownie.";

/** Matches the backend's `core/errors.py::error_payload` envelope exactly,
 * so a request blocked client-side is indistinguishable, on the wire shape,
 * from one the API itself would have rejected. */
export const DEMO_READ_ONLY_ERROR_CODE = "demo_read_only";
