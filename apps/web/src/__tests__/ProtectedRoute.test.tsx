import { describe, it, expect, beforeEach, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import { MemoryRouter, Routes, Route } from "react-router-dom";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { useAuthStore } from "@/shared/store/authStore";
import { ProtectedRoute } from "@/app/router";

// Mock AppShell to avoid deep component tree and avoid lazy-loading dependencies
vi.mock("@/shared/ui/AppShell", () => ({
  AppShell: ({ children }: { children: React.ReactNode }) => (
    <div data-testid="app-shell">{children}</div>
  ),
}));

function TestApp({ initialPath }: { initialPath: string }) {
  const queryClient = new QueryClient({
    defaultOptions: {
      queries: { retry: false },
    },
  });

  return (
    <QueryClientProvider client={queryClient}>
      <MemoryRouter initialEntries={[initialPath]}>
        <Routes>
          <Route path="/login" element={<div>Login Page</div>} />
          <Route element={<ProtectedRoute />}>
            <Route path="/dashboard" element={<div>Dashboard</div>} />
          </Route>
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>
  );
}

beforeEach(() => {
  useAuthStore.setState({ accessToken: null, refreshToken: null, user: null });
  localStorage.clear();
});

describe("ProtectedRoute", () => {
  it("redirects to /login when not authenticated", () => {
    render(<TestApp initialPath="/dashboard" />);
    expect(screen.getByText("Login Page")).toBeInTheDocument();
    expect(screen.queryByText("Dashboard")).not.toBeInTheDocument();
  });

  it("renders children in AppShell when authenticated", () => {
    useAuthStore.setState({ accessToken: "tok", refreshToken: null, user: null });
    render(<TestApp initialPath="/dashboard" />);
    expect(screen.getByText("Dashboard")).toBeInTheDocument();
    expect(screen.getByTestId("app-shell")).toBeInTheDocument();
    expect(screen.queryByText("Login Page")).not.toBeInTheDocument();
  });
});
