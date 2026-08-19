import { describe, it, expect, beforeEach } from "vitest";
import { useAuthStore } from "@/shared/store/authStore";
import type { User } from "@/shared/types";

const mockUser: User = {
  id: "00000000-0000-0000-0000-000000000001",
  email: "test@example.com",
  full_name: "Test User",
  avatar_url: null,
  timezone: null,
  created_at: "2024-01-01T00:00:00Z",
  updated_at: "2024-01-01T00:00:00Z",
};

beforeEach(() => {
  localStorage.clear();
  useAuthStore.setState({ accessToken: null, user: null });
});

describe("useAuthStore", () => {
  it("starts with no auth", () => {
    const { accessToken, user } = useAuthStore.getState();
    expect(accessToken).toBeNull();
    expect(user).toBeNull();
  });

  it("login sets token and user", () => {
    useAuthStore.getState().login("access-123", mockUser);
    const { accessToken, user } = useAuthStore.getState();
    expect(accessToken).toBe("access-123");
    expect(user?.email).toBe("test@example.com");
  });

  it("logout clears everything", () => {
    useAuthStore.getState().login("access-123", mockUser);
    useAuthStore.getState().logout();
    const { accessToken, user } = useAuthStore.getState();
    expect(accessToken).toBeNull();
    expect(user).toBeNull();
  });

  it("setToken updates accessToken", () => {
    useAuthStore.getState().login("old", mockUser);
    useAuthStore.getState().setToken("new-access");
    expect(useAuthStore.getState().accessToken).toBe("new-access");
  });

  it("setUser updates user", () => {
    useAuthStore.getState().login("access-123", mockUser);
    const updated = { ...mockUser, full_name: "Updated User" };
    useAuthStore.getState().setUser(updated);
    expect(useAuthStore.getState().user?.full_name).toBe("Updated User");
  });
});
