/**
 * `IS_DEMO` is a module-level constant baked in at import time — see
 * LoginForm.demo.test.tsx for why this needs `vi.stubEnv` + a fresh
 * dynamic import rather than a plain top-level one.
 */
import { afterEach, describe, expect, it, vi } from "vitest";
import { render, screen } from "@testing-library/react";

async function renderFreshDemoBanner() {
  vi.resetModules();
  const { DemoBanner } = await import("@/shared/ui/DemoBanner");
  return render(<DemoBanner />);
}

describe("DemoBanner", () => {
  afterEach(() => {
    vi.unstubAllEnvs();
  });

  it("renders the read-only notice in demo mode", async () => {
    vi.stubEnv("VITE_DEMO_MODE", "true");
    await renderFreshDemoBanner();
    expect(screen.getByRole("status")).toHaveTextContent(/wersja demonstracyjna/i);
  });

  it("renders nothing outside demo mode", async () => {
    const { container } = await renderFreshDemoBanner();
    expect(container).toBeEmptyDOMElement();
  });
});
