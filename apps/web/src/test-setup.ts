import "@testing-library/jest-dom";
import { afterAll, afterEach, beforeAll } from "vitest";
import { server } from "./__tests__/mocks/server";

beforeAll(() => server.listen({ onUnhandledRequest: "bypass" }));
afterEach(() => server.resetHandlers());
afterAll(() => server.close());

// jsdom doesn't implement the Pointer Events capture API that Radix UI's
// interactive components (Select, Dialog, etc.) rely on for pointer-driven
// open/close behavior. Stub it so userEvent.click() on those components
// doesn't throw "hasPointerCapture is not a function" in tests.
if (typeof Element !== "undefined") {
  if (!Element.prototype.hasPointerCapture) {
    Element.prototype.hasPointerCapture = () => false;
  }
  if (!Element.prototype.setPointerCapture) {
    Element.prototype.setPointerCapture = () => {};
  }
  if (!Element.prototype.releasePointerCapture) {
    Element.prototype.releasePointerCapture = () => {};
  }
}

// jsdom also doesn't implement scrollIntoView, which Radix Select calls
// when scrolling the highlighted item into view.
if (typeof Element !== "undefined" && !Element.prototype.scrollIntoView) {
  Element.prototype.scrollIntoView = () => {};
}

// Provide a localStorage stub for test environments where jsdom's localStorage
// is not available (e.g. when running under Node without a localstorage-file).
if (typeof localStorage === "undefined" || localStorage === null) {
  const localStorageMock = (() => {
    let store: Record<string, string> = {};
    return {
      getItem: (key: string): string | null => store[key] ?? null,
      setItem: (key: string, value: string): void => {
        store[key] = value;
      },
      removeItem: (key: string): void => {
        delete store[key];
      },
      clear: (): void => {
        store = {};
      },
      get length(): number {
        return Object.keys(store).length;
      },
      key: (index: number): string | null =>
        Object.keys(store)[index] ?? null,
    };
  })();
  Object.defineProperty(globalThis, "localStorage", {
    value: localStorageMock,
    writable: true,
  });
}
