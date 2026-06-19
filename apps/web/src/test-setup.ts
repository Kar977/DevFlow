import "@testing-library/jest-dom";

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
