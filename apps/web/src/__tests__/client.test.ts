/**
 * @vitest-environment node
 *
 * Runs in Node so MSW's http/https interceptors work correctly with
 * axios's Node adapter. The jsdom XHR adapter cannot be intercepted by MSW.
 */
import { describe, it, expect, beforeEach, afterEach, vi } from "vitest";
import axios from "axios";
import { http, HttpResponse } from "msw";
import { server } from "./mocks/server";
import { apiClient } from "@/shared/api/client";
import { useAuthStore } from "@/shared/store/authStore";

const mockUser = {
  id: "user-1",
  email: "test@example.com",
  name: "Test User",
};

// In node env, window doesn't exist — we need a global location mock
// for the interceptor that sets window.location.href = "/login"
let locationMock: { href: string };

beforeEach(() => {
  useAuthStore.setState({ accessToken: null, refreshToken: null, user: null });
  locationMock = { href: "" };
  // Provide window.location for the interceptor code (Node env has no window)
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  (global as any).window = { location: locationMock };
  // Patch apiClient to use an absolute baseURL so axios can resolve it in Node
  apiClient.defaults.baseURL = "http://localhost/api/v1";
  // The refresh call in client.ts uses bare axios.post("/api/v1/auth/refresh"),
  // which needs a base URL in Node (browsers resolve relative to page origin).
  axios.defaults.baseURL = "http://localhost";
});

afterEach(() => {
  vi.restoreAllMocks();
});

describe("apiClient — request interceptor", () => {
  it("attaches Authorization: Bearer header when an access token is set", async () => {
    useAuthStore.getState().login("tok-abc", "ref-xyz", mockUser);

    let capturedHeader: string | null = null;
    server.use(
      http.get("http://localhost/api/v1/tasks", ({ request }) => {
        capturedHeader = request.headers.get("Authorization");
        return HttpResponse.json({ items: [] });
      })
    );

    await apiClient.get("/tasks");
    expect(capturedHeader).toBe("Bearer tok-abc");
  });

  it("does not attach Authorization header when no token is set", async () => {
    let capturedHeader: string | null | undefined = undefined;
    server.use(
      http.get("http://localhost/api/v1/tasks", ({ request }) => {
        capturedHeader = request.headers.get("Authorization");
        return HttpResponse.json({ items: [] });
      })
    );

    await apiClient.get("/tasks");
    expect(capturedHeader).toBeNull();
  });
});

describe("apiClient — response interceptor (401 handling)", () => {
  it("calls logout() and redirects to /login when 401 and no refresh token", async () => {
    useAuthStore.setState({
      accessToken: "bad-tok",
      refreshToken: null,
      user: mockUser,
    });

    server.use(
      http.get("http://localhost/api/v1/tasks", () =>
        HttpResponse.json({ detail: "Unauthorized" }, { status: 401 })
      )
    );

    await expect(apiClient.get("/tasks")).rejects.toThrow();

    expect(useAuthStore.getState().accessToken).toBeNull();
    expect(locationMock.href).toBe("/login");
  });

  it("calls POST /api/v1/auth/refresh and retries the original request when 401 with refresh token", async () => {
    useAuthStore.getState().login("expired-tok", "valid-refresh", mockUser);

    let tasksCallCount = 0;
    server.use(
      http.get("http://localhost/api/v1/tasks", () => {
        tasksCallCount++;
        if (tasksCallCount === 1) {
          return HttpResponse.json({ detail: "Unauthorized" }, { status: 401 });
        }
        return HttpResponse.json({ items: ["task1"] });
      }),
      http.post("http://localhost/api/v1/auth/refresh", async ({ request }) => {
        const body = (await request.json()) as { refresh_token: string };
        expect(body.refresh_token).toBe("valid-refresh");
        return HttpResponse.json({ access_token: "new-tok-123" });
      })
    );

    const response = await apiClient.get("/tasks");

    expect(response.data).toEqual({ items: ["task1"] });
    expect(useAuthStore.getState().accessToken).toBe("new-tok-123");
    expect(tasksCallCount).toBe(2);
  });

  it("calls logout() and redirects to /login when refresh call fails", async () => {
    useAuthStore.getState().login("expired-tok", "bad-refresh", mockUser);

    server.use(
      http.get("http://localhost/api/v1/tasks", () =>
        HttpResponse.json({ detail: "Unauthorized" }, { status: 401 })
      ),
      http.post("http://localhost/api/v1/auth/refresh", () =>
        HttpResponse.json({ detail: "Invalid refresh token" }, { status: 401 })
      )
    );

    await expect(apiClient.get("/tasks")).rejects.toThrow();

    expect(useAuthStore.getState().accessToken).toBeNull();
    expect(locationMock.href).toBe("/login");
  });
});
