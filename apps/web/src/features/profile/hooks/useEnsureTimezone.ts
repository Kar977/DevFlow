import { useEffect, useRef } from "react";
import { apiClient } from "@/shared/api/client";
import { useAuthStore } from "@/shared/store/authStore";
import type { User } from "@/shared/types";

/**
 * One-time auto-detect-and-persist of the browser's IANA timezone.
 *
 * Every metrics bucket (day/week) is computed in the user's stored
 * `timezone`, defaulting to UTC when it's `null` — which it is for every
 * account that predates this feature, and for a freshly registered one.
 * Rather than making the user hunt for a settings toggle, this fires once
 * per session when `user.timezone` is still null and PATCHes the detected
 * zone to `/auth/me`, so the dashboard is correctly bucketed without any
 * action on their part. `Intl.DateTimeFormat().resolvedOptions().timeZone`
 * is standard in every supported browser and Node/jsdom.
 */
export function useEnsureTimezone(): void {
  const user = useAuthStore((s) => s.user);
  const setUser = useAuthStore((s) => s.setUser);
  const attempted = useRef(false);

  useEffect(() => {
    if (!user || user.timezone !== null || attempted.current) return;
    attempted.current = true;

    const detected = Intl.DateTimeFormat().resolvedOptions().timeZone;
    if (!detected) return;

    void apiClient
      .patch("/auth/me", { timezone: detected })
      .then((r) => setUser(r.data as User))
      .catch(() => {
        // Best-effort: leave timezone null (UTC bucketing) and let this
        // retry next session rather than surface an error for a background
        // convenience action the user didn't initiate.
      });
  }, [user, setUser]);
}
