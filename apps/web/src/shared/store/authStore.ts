import { create } from "zustand";
import { persist } from "zustand/middleware";
import type { User } from "@/shared/types";

// The refresh token is never held here — it is set by the backend as an
// httpOnly cookie (see shared/api/client.ts), so it is not readable from JS
// and therefore not exposed to XSS. Only the short-lived access token and
// the user profile are kept in this JS-readable store.
type AuthState = {
  accessToken: string | null;
  user: User | null;
};

type AuthActions = {
  login: (accessToken: string, user: User) => void;
  logout: () => void;
  setToken: (accessToken: string) => void;
  setUser: (user: User) => void;
};

export const useAuthStore = create<AuthState & AuthActions>()(
  persist(
    (set) => ({
      accessToken: null,
      user: null,
      login: (accessToken, user) => set({ accessToken, user }),
      logout: () => set({ accessToken: null, user: null }),
      setToken: (accessToken) => set({ accessToken }),
      setUser: (user) => set({ user }),
    }),
    {
      name: "devflow-auth",
      // Only persist the access token and user — nothing else from the store
      partialize: (state) => ({
        accessToken: state.accessToken,
        user: state.user,
      }),
    }
  )
);
