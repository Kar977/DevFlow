/**
 * @vitest-environment node
 *
 * Runs in Node so MSW's http/https interceptors work correctly with
 * axios's Node adapter (see client.test.ts for the same rationale).
 *
 * `IS_DEMO` is a module-level constant read from `import.meta.env` at
 * import time (see shared/lib/demo.ts). Demo mode no longer installs any
 * client-side write guard — writes reach the network exactly like outside
 * demo mode — so these tests just confirm that stays true whether or not
 * `VITE_DEMO_MODE` is set, using the same `vi.stubEnv` + fresh dynamic
 * import pattern the rest of the demo-mode tests use.
 */
import { afterEach, describe, expect, it, vi } from "vitest";
import { http, HttpResponse } from "msw";
import { server } from "./mocks/server";

async function freshApiClient() {
  vi.resetModules();
  const { apiClient } = await import("@/shared/api/client");
  // Node has no page origin to resolve a relative baseURL against.
  apiClient.defaults.baseURL = "http://localhost/api/v1";
  return apiClient;
}

describe("apiClient — demo mode (VITE_DEMO_MODE=true)", () => {
  afterEach(() => {
    vi.unstubAllEnvs();
  });

  it("lets a mutating request reach the network, same as outside demo mode", async () => {
    vi.stubEnv("VITE_DEMO_MODE", "true");
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

  it("lets PATCH and DELETE through too", async () => {
    vi.stubEnv("VITE_DEMO_MODE", "true");
    server.use(
      http.patch("http://localhost/api/v1/tasks/1", () => HttpResponse.json({ id: "1" })),
      http.delete("http://localhost/api/v1/tasks/1", () => new HttpResponse(null, { status: 204 }))
    );
    const apiClient = await freshApiClient();

    await expect(apiClient.patch("/tasks/1", {})).resolves.toMatchObject({
      data: { id: "1" },
    });
    await expect(apiClient.delete("/tasks/1")).resolves.toMatchObject({ status: 204 });
  });

  it("lets POST /auth/login through", async () => {
    vi.stubEnv("VITE_DEMO_MODE", "true");
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

  it("still lets registration reach the network (the backend blocks it, not the client)", async () => {
    vi.stubEnv("VITE_DEMO_MODE", "true");
    let called = false;
    server.use(
      http.post("http://localhost/api/v1/auth/register", () => {
        called = true;
        return HttpResponse.json(
          { error: { code: "demo_read_only", message: "x", details: {} } },
          { status: 403 }
        );
      })
    );
    const apiClient = await freshApiClient();

    await expect(
      apiClient.post("/auth/register", { email: "x@example.com", password: "x" })
    ).rejects.toMatchObject({
      response: { status: 403, data: { error: { code: "demo_read_only" } } },
    });
    expect(called).toBe(true);
  });
});

describe("apiClient — outside demo mode", () => {
  it("behaves identically — writes reach the network", async () => {
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
