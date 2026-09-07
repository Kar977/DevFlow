import axios, { type AxiosError, type InternalAxiosRequestConfig } from "axios";
import { useAuthStore } from "@/shared/store/authStore";
import {
  DEMO_READ_ONLY_ERROR_CODE,
  DEMO_READ_ONLY_TOAST_MESSAGE,
  IS_DEMO,
} from "@/shared/lib/demo";

export const apiClient = axios.create({
  baseURL: "/api/v1",
  headers: { "Content-Type": "application/json" },
  // Send/receive the httpOnly refresh-token cookie set by the backend.
  withCredentials: true,
});

apiClient.interceptors.request.use((config: InternalAxiosRequestConfig) => {
  const token = useAuthStore.getState().accessToken;
  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

// Read-only public showcase mode (see shared/lib/demo.ts): every mutating
// request is stopped here, before it leaves the browser, and rejected with
// a synthetic error shaped exactly like the real 403 the backend's
// DemoReadOnlyMiddleware would return — so getErrorMessage() and every
// existing mutation's own error handling need no changes to surface it.
// Login/refresh/logout are exempt so a visitor can still authenticate; the
// backend enforces the identical exemption independently.
const DEMO_SAFE_METHODS = new Set(["get", "head", "options"]);
const DEMO_ALLOWED_WRITE_PATHS = new Set([
  "/auth/login",
  "/auth/refresh",
  "/auth/logout",
]);

if (IS_DEMO) {
  apiClient.interceptors.request.use((config: InternalAxiosRequestConfig) => {
    const method = (config.method ?? "get").toLowerCase();
    if (DEMO_SAFE_METHODS.has(method) || DEMO_ALLOWED_WRITE_PATHS.has(config.url ?? "")) {
      return config;
    }
    return Promise.reject(
      new axios.AxiosError(
        DEMO_READ_ONLY_TOAST_MESSAGE,
        "ERR_DEMO_READ_ONLY",
        config,
        undefined,
        {
          status: 403,
          statusText: "Forbidden",
          headers: {},
          config,
          data: {
            error: {
              code: DEMO_READ_ONLY_ERROR_CODE,
              message: DEMO_READ_ONLY_TOAST_MESSAGE,
              details: {},
            },
          },
        } as unknown as AxiosError["response"]
      )
    );
  });
}

let isRefreshing = false;
let failedQueue: Array<{
  resolve: (value: string) => void;
  reject: (reason: unknown) => void;
}> = [];

function processQueue(error: unknown, token: string | null) {
  for (const prom of failedQueue) {
    if (error) prom.reject(error);
    else prom.resolve(token!);
  }
  failedQueue = [];
}

apiClient.interceptors.response.use(
  (response) => response,
  async (error: AxiosError) => {
    const originalRequest = error.config as InternalAxiosRequestConfig & { _retry?: boolean };

    if (error.response?.status !== 401 || originalRequest._retry) {
      return Promise.reject(error);
    }

    const { setToken, logout } = useAuthStore.getState();

    if (isRefreshing) {
      return new Promise<string>((resolve, reject) => {
        failedQueue.push({ resolve, reject });
      }).then((token) => {
        originalRequest.headers.Authorization = `Bearer ${token}`;
        return apiClient(originalRequest);
      });
    }

    originalRequest._retry = true;
    isRefreshing = true;

    try {
      const response = await axios.post<{ access_token: string }>(
        "/api/v1/auth/refresh",
        null,
        { withCredentials: true }
      );
      const newToken = response.data.access_token;
      setToken(newToken);
      processQueue(null, newToken);
      originalRequest.headers.Authorization = `Bearer ${newToken}`;
      return apiClient(originalRequest);
    } catch (refreshError) {
      processQueue(refreshError, null);
      logout();
      window.location.href = "/login";
      return Promise.reject(refreshError);
    } finally {
      isRefreshing = false;
    }
  }
);
