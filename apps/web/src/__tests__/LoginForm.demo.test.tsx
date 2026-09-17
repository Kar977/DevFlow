/**
 * Demo-mode variant of LoginForm.test.tsx. `IS_DEMO` is a module-level
 * constant read from `import.meta.env` at import time (shared/lib/demo.ts),
 * so exercising it requires `vi.stubEnv` *before* a fresh dynamic import of
 * the component — the plain top-level import in LoginForm.test.tsx always
 * sees VITE_DEMO_MODE unset.
 */
import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { MemoryRouter } from "react-router-dom";

const mutate = vi.fn();
vi.mock("@/features/auth/hooks/useLoginMutation", () => ({
  useLoginMutation: () => ({ mutate, isPending: false, error: null }),
}));

async function renderDemoLoginForm() {
  vi.resetModules();
  const { LoginForm } = await import("@/features/auth/components/LoginForm");
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={qc}>
      <MemoryRouter>
        <LoginForm />
      </MemoryRouter>
    </QueryClientProvider>
  );
}

describe("LoginForm — demo mode", () => {
  beforeEach(() => {
    vi.stubEnv("VITE_DEMO_MODE", "true");
    mutate.mockClear();
  });

  afterEach(() => {
    vi.unstubAllEnvs();
  });

  it("shows the demo intro and a 'Wejdź do demo' button", async () => {
    await renderDemoLoginForm();
    expect(screen.getAllByText(/wersja demonstracyjna/i).length).toBeGreaterThan(0);
    expect(screen.getByRole("button", { name: /wejdź do demo/i })).toBeInTheDocument();
  });

  it("logs in with the shared demo credentials when clicked", async () => {
    await renderDemoLoginForm();
    await userEvent.click(screen.getByRole("button", { name: /wejdź do demo/i }));
    expect(mutate).toHaveBeenCalledWith({
      email: "demo@devflow.app",
      password: "DevFlowDemo2026!",
    });
  });

  it("does not render the regular email/password login form", async () => {
    await renderDemoLoginForm();
    expect(screen.queryByLabelText("E-mail")).not.toBeInTheDocument();
    expect(screen.queryByLabelText("Hasło")).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /^zaloguj się$/i })).not.toBeInTheDocument();
  });

  it("hides the registration link", async () => {
    await renderDemoLoginForm();
    expect(screen.queryByRole("link", { name: /zarejestruj/i })).not.toBeInTheDocument();
  });

  it("shows a warning that the backend may need a few minutes to wake up", async () => {
    await renderDemoLoginForm();
    expect(screen.getByText(/kilka minut/i)).toBeInTheDocument();
  });
});
