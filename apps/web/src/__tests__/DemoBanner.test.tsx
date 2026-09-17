/**
 * `IS_DEMO` is a module-level constant baked in at import time — see
 * LoginForm.demo.test.tsx for why this needs `vi.stubEnv` + a fresh
 * dynamic import rather than a plain top-level one.
 */
import { afterEach, describe, expect, it, vi } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { http, HttpResponse } from "msw";
import { server } from "./mocks/server";

async function renderFreshDemoBanner() {
  vi.resetModules();
  const { DemoBanner } = await import("@/shared/ui/DemoBanner");
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={qc}>
      <DemoBanner />
    </QueryClientProvider>
  );
}

describe("DemoBanner", () => {
  afterEach(() => {
    vi.unstubAllEnvs();
  });

  it("renders the editable-showcase notice in demo mode", async () => {
    vi.stubEnv("VITE_DEMO_MODE", "true");
    await renderFreshDemoBanner();
    expect(screen.getByRole("status")).toHaveTextContent(/wersja demonstracyjna/i);
  });

  it("renders nothing outside demo mode", async () => {
    const { container } = await renderFreshDemoBanner();
    expect(container).toBeEmptyDOMElement();
  });

  it("shows a countdown to the next data reset once /demo/status resolves", async () => {
    vi.stubEnv("VITE_DEMO_MODE", "true");
    const nextReset = new Date(Date.now() + 17 * 60_000).toISOString();
    server.use(
      http.get("*/demo/status", () =>
        HttpResponse.json({
          enabled: true,
          reset_interval_minutes: 30,
          next_reset_at: nextReset,
        })
      )
    );

    await renderFreshDemoBanner();

    await waitFor(() =>
      expect(screen.getByRole("status")).toHaveTextContent(/reset danych/i)
    );
  });
});
