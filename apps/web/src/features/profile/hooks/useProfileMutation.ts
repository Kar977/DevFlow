import { useMutation, useQueryClient } from "@tanstack/react-query";
import { apiClient } from "@/shared/api/client";
import { useAuthStore } from "@/shared/store/authStore";
import { metricsQueryKeys } from "@/features/metrics/hooks/metricsQueryKeys";
import type { User } from "@/shared/types";

export interface UpdateProfileData {
  full_name?: string;
  avatar_url?: string;
  timezone?: string;
}

export function useProfileMutation() {
  const qc = useQueryClient();
  const currentUser = useAuthStore((s) => s.user);
  const setUser = useAuthStore((s) => s.setUser);

  return useMutation({
    mutationFn: (data: UpdateProfileData) =>
      apiClient.patch("/auth/me", data).then((r) => r.data as User),
    onSuccess: (user, variables) => {
      setUser(user);

      const timezoneChanged =
        variables.timezone !== undefined && variables.timezone !== currentUser?.timezone;
      if (!timezoneChanged) return;

      // The user's week/day grid just shifted — every metrics panel and the
      // long-range trend snapshots need to reflect the new zone.
      void qc.invalidateQueries({ queryKey: metricsQueryKeys.all });
      void apiClient.post("/metrics/trends/recompute").catch(() => {
        // Best-effort: the live panels are already correct via the
        // invalidation above (their cache key includes the tz name); a
        // failed recompute just means /trends keeps last zone's history a
        // little longer, not an error worth surfacing to the user.
      });
    },
  });
}
