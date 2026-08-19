import { useQuery } from "@tanstack/react-query";
import { apiClient } from "@/shared/api/client";
import { SummarySchema, VelocitySchema } from "@/shared/api/schemas/metrics";
import { daysAgoLocal, todayLocal } from "@/shared/lib/localDate";
import { metricsQueryKeys } from "@/features/metrics/hooks/metricsQueryKeys";
import type { DashboardWindow } from "../lib/period";

/**
 * @param window Overrides the default 30-day trailing window (e.g. with the
 * dashboard's shared sprint period). Omitted entirely, callers keep today's
 * behaviour unchanged — this is what makes the parameter optional rather
 * than required.
 * @param enabled Gates both queries — defaults to `true`. Pass `false` while
 * `window` is still resolving so a fetch doesn't fire against the 30-day
 * fallback for a caller that actually wants a different, not-yet-known
 * window (the dashboard, waiting on the sprint series).
 */
export function useDashboardData(
  organizationId?: string,
  memberUserId?: string,
  window?: DashboardWindow,
  enabled = true
) {
  const date_to = window?.date_to ?? todayLocal();
  const date_from = window?.date_from ?? daysAgoLocal(30);
  const params = {
    date_from,
    date_to,
    ...(organizationId ? { organization_id: organizationId } : {}),
    ...(memberUserId ? { member_user_id: memberUserId } : {}),
  };

  const { data: summary, isLoading: summaryLoading } = useQuery({
    queryKey: [...metricsQueryKeys.all, "summary", params],
    enabled,
    queryFn: () =>
      apiClient
        .get("/metrics/summary", { params })
        .then((r) => SummarySchema.parse(r.data)),
  });

  const { data: velocity, isLoading: velocityLoading } = useQuery({
    queryKey: [...metricsQueryKeys.all, "velocity", params],
    enabled,
    queryFn: () =>
      apiClient
        .get("/metrics/velocity", { params })
        .then((r) => VelocitySchema.parse(r.data)),
  });

  return {
    summary,
    velocity,
    isLoading: !enabled || summaryLoading || velocityLoading,
  };
}
