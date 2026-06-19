import { describe, it, expect, beforeEach } from "vitest";
import { render, screen } from "@testing-library/react";
import { MemoryRouter, Routes, Route, Navigate } from "react-router-dom";
import { useAuthStore } from "@/shared/store/authStore";

function ProtectedRoute({ children }: { children: React.ReactNode }) {
  const token = useAuthStore((s) => s.accessToken);
  if (!token) return <Navigate to="/login" replace />;
  return <>{children}</>;
}

function TestApp({ initialPath }: { initialPath: string }) {
  return (
    <MemoryRouter initialEntries={[initialPath]}>
      <Routes>
        <Route path="/login" element={<div>Login Page</div>} />
        <Route
          path="/dashboard"
          element={
            <ProtectedRoute>
              <div>Dashboard</div>
            </ProtectedRoute>
          }
        />
      </Routes>
    </MemoryRouter>
  );
}

beforeEach(() => {
  useAuthStore.setState({ accessToken: null, refreshToken: null, user: null });
});

describe("ProtectedRoute", () => {
  it("redirects to /login when not authenticated", () => {
    render(<TestApp initialPath="/dashboard" />);
    expect(screen.getByText("Login Page")).toBeInTheDocument();
  });

  it("renders children when authenticated", () => {
    useAuthStore.setState({ accessToken: "tok", refreshToken: null, user: null });
    render(<TestApp initialPath="/dashboard" />);
    expect(screen.getByText("Dashboard")).toBeInTheDocument();
  });
});
