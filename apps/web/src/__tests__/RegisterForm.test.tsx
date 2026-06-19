import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { MemoryRouter } from "react-router-dom";
import { RegisterForm } from "@/features/auth/components/RegisterForm";

vi.mock("@/features/auth/hooks/useRegisterMutation", () => ({
  useRegisterMutation: () => ({ mutate: vi.fn(), isPending: false, error: null }),
}));

function renderRegisterForm() {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={qc}>
      <MemoryRouter>
        <RegisterForm />
      </MemoryRouter>
    </QueryClientProvider>
  );
}

beforeEach(() => vi.clearAllMocks());

describe("RegisterForm", () => {
  it("renders all fields", () => {
    renderRegisterForm();
    expect(screen.getByLabelText("Imię i nazwisko")).toBeInTheDocument();
    expect(screen.getByLabelText("E-mail")).toBeInTheDocument();
    expect(screen.getByLabelText("Hasło")).toBeInTheDocument();
  });

  it("shows password length error when password too short", async () => {
    renderRegisterForm();
    await userEvent.type(screen.getByLabelText("Imię i nazwisko"), "Jan Kowalski");
    await userEvent.type(screen.getByLabelText("E-mail"), "jan@example.com");
    await userEvent.type(screen.getByLabelText("Hasło"), "short");
    await userEvent.click(screen.getByRole("button", { name: /zarejestruj/i }));
    expect(await screen.findByText(/co najmniej 8 znaków/i)).toBeInTheDocument();
  });

  it("shows link to login page", () => {
    renderRegisterForm();
    expect(screen.getByRole("link", { name: /zaloguj/i })).toHaveAttribute("href", "/login");
  });
});
