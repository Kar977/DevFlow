/**
 * `IS_DEMO` is a module-level constant baked in at import time
 * (shared/lib/demo.ts), so exercising router.tsx's demo-only `/register`
 * redirect needs `vi.stubEnv` *before* a fresh dynamic import of the router
 * module — see LoginForm.demo.test.tsx and demoReadOnly.test.ts for the
 * same pattern.
 *
 * Asserts the route *configuration* directly (rather than mounting
 * `RouterProvider` and driving real navigation) — `createBrowserRouter`'s
 * data-router internals reach for `fetch`/`AbortSignal` in ways jsdom+MSW
 * don't reliably support, which is orthogonal to the one-line ternary this
 * test actually needs to cover.
 */
import { afterEach, describe, expect, it, vi } from "vitest";
import { Navigate } from "react-router-dom";
import type { ReactElement } from "react";

interface RouteWithElement {
  path?: string;
  element?: ReactElement;
}

async function registerRoute(): Promise<RouteWithElement> {
  vi.resetModules();
  const { router } = await import("@/app/router");
  const routes = router.routes as RouteWithElement[];
  const route = routes.find((r) => r.path === "/register");
  if (!route) throw new Error("/register route not found");
  return route;
}

describe("router — /register (demo mode)", () => {
  afterEach(() => {
    vi.unstubAllEnvs();
  });

  it("redirects to /login instead of rendering the registration form", async () => {
    vi.stubEnv("VITE_DEMO_MODE", "true");
    const route = await registerRoute();
    expect(route.element?.type).toBe(Navigate);
    expect(route.element?.props).toMatchObject({ to: "/login", replace: true });
  });
});

describe("router — /register (outside demo mode)", () => {
  it("renders the real registration page", async () => {
    // Both imports must come from the same fresh module registry — importing
    // RegisterPage before `registerRoute()`'s own `vi.resetModules()` would
    // compare against a stale instance and fail Object.is by construction.
    vi.resetModules();
    const [{ router }, { RegisterPage }] = await Promise.all([
      import("@/app/router"),
      import("@/features/auth/pages/RegisterPage"),
    ]);
    const routes = router.routes as RouteWithElement[];
    const route = routes.find((r) => r.path === "/register");
    expect(route?.element?.type).toBe(RegisterPage);
  });
});
