import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { MemoryRouter } from "react-router-dom";
import { LoginForm } from "@/features/auth/components/LoginForm";

vi.mock("@/features/auth/hooks/useLoginMutation", () => ({
  useLoginMutation: () => ({ mutate: vi.fn(), isPending: false, error: null }),
}));

function renderLoginForm() {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={qc}>
      <MemoryRouter>
        <LoginForm />
      </MemoryRouter>
    </QueryClientProvider>
  );
}

beforeEach(() => vi.clearAllMocks());

describe("LoginForm", () => {
  it("renders email and password fields", () => {
    renderLoginForm();
    expect(screen.getByLabelText("E-mail")).toBeInTheDocument();
    expect(screen.getByLabelText("Hasło")).toBeInTheDocument();
  });

  it("shows validation error for empty email on submit", async () => {
    renderLoginForm();
    await userEvent.click(screen.getByRole("button", { name: "Zaloguj się" }));
    expect(await screen.findByText(/poprawny adres e-mail/i)).toBeInTheDocument();
  });

  it("shows link to register page", () => {
    renderLoginForm();
    expect(screen.getByRole("link", { name: /zarejestruj/i })).toHaveAttribute("href", "/register");
  });
});
