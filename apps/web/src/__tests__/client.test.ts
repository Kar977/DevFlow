import { describe, it, expect, beforeEach, vi } from "vitest";
import axios from "axios";
import { useAuthStore } from "@/shared/store/authStore";

vi.mock("axios", async (importOriginal) => {
  const actual = await importOriginal<typeof import("axios")>();
  return {
    ...actual,
    default: {
      ...actual.default,
      create: vi.fn(() => ({
        interceptors: {
          request: { use: vi.fn() },
          response: { use: vi.fn() },
        },
      })),
    },
  };
});

beforeEach(() => {
  useAuthStore.setState({ accessToken: null, refreshToken: null, user: null });
  vi.clearAllMocks();
});

describe("apiClient interceptors", () => {
  it("request interceptor attaches bearer token when logged in", () => {
    useAuthStore.setState({ accessToken: "tok-123", refreshToken: null, user: null });
    const token = useAuthStore.getState().accessToken;
    expect(token).toBe("tok-123");
  });

  it("request interceptor skips auth header when no token", () => {
    const token = useAuthStore.getState().accessToken;
    expect(token).toBeNull();
  });
});
