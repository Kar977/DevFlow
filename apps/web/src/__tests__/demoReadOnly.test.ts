/**
 * @vitest-environment node
 *
 * Runs in Node so MSW's http/https interceptors work correctly with
 * axios's Node adapter (see client.test.ts for the same rationale).
 *
 * `IS_DEMO` is a module-level constant read from `import.meta.env` at
 * import time (see shared/lib/demo.ts), so exercising the demo-mode branch
 * requires `vi.stubEnv` *before* a fresh dynamic import of client.ts —
 * merely stubbing the env after the module has already loaded elsewhere
 * in the suite would have no effect.
 */
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { http, HttpResponse } from "msw";
import { server } from "./mocks/server";

async function freshApiClient() {
  vi.resetModules();
  const { apiClient } = await import("@/shared/api/client");
  // Node has no page origin to resolve a relative baseURL against.
  apiClient.defaults.baseURL = "http://localhost/api/v1";
  return apiClient;
}

describe("apiClient — demo read-only guard (VITE_DEMO_MODE=true)", () => {
  beforeEach(() => {
    vi.stubEnv("VITE_DEMO_MODE", "true");
  });

  afterEach(() => {
    vi.unstubAllEnvs();
  });

  it("blocks a mutating request without it ever reaching the network", async () => {
    let called = false;
    server.use(
      http.post("http://localhost/api/v1/tasks", () => {
        called = true;
        return HttpResponse.json({ id: "should-not-happen" });
      })
    );
    const apiClient = await freshApiClient();

    await expect(apiClient.post("/tasks", { title: "x" })).rejects.toMatchObject({
      response: {
        status: 403,
        data: { error: { code: "demo_read_only" } },
      },
    });
    expect(called).toBe(false);
  });

  it("does not block GET requests", async () => {
    server.use(
      http.get("http://localhost/api/v1/tasks", () => HttpResponse.json({ items: [] }))
    );
    const apiClient = await freshApiClient();

    const response = await apiClient.get("/tasks");
    expect(response.data).toEqual({ items: [] });
  });

  it("lets POST /auth/login through", async () => {
    server.use(
      http.post("http://localhost/api/v1/auth/login", () =>
        HttpResponse.json({ access_token: "tok" })
      )
    );
    const apiClient = await freshApiClient();

    const response = await apiClient.post("/auth/login", {
      email: "demo@devflow.app",
      password: "x",
    });
    expect(response.data).toEqual({ access_token: "tok" });
  });

  it("lets POST /auth/refresh and /auth/logout through", async () => {
    server.use(
      http.post("http://localhost/api/v1/auth/refresh", () =>
        HttpResponse.json({ access_token: "tok" })
      ),
      http.post("http://localhost/api/v1/auth/logout", () => new HttpResponse(null, { status: 204 }))
    );
    const apiClient = await freshApiClient();

    await expect(apiClient.post("/auth/refresh")).resolves.toMatchObject({
      data: { access_token: "tok" },
    });
    await expect(apiClient.post("/auth/logout")).resolves.toMatchObject({ status: 204 });
  });

  it("blocks PATCH and DELETE too", async () => {
    const apiClient = await freshApiClient();

    await expect(apiClient.patch("/tasks/1", {})).rejects.toMatchObject({
      response: { status: 403 },
    });
    await expect(apiClient.delete("/tasks/1")).rejects.toMatchObject({
      response: { status: 403 },
    });
  });
});

describe("apiClient — outside demo mode", () => {
  it("does not install the read-only guard", async () => {
    let called = false;
    server.use(
      http.post("http://localhost/api/v1/tasks", () => {
        called = true;
        return HttpResponse.json({ id: "created" });
      })
    );
    const apiClient = await freshApiClient();

    const response = await apiClient.post("/tasks", { title: "x" });
    expect(response.data).toEqual({ id: "created" });
    expect(called).toBe(true);
  });
});
