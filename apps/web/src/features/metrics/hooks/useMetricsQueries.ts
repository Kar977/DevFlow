import { useQuery } from "@tanstack/react-query";
import { apiClient } from "@/shared/api/client";
import {
  VelocitySchema,
  TimeTrackingSchema,
  CompletionRateSchema,
  EstimationAccuracySchema,
  StreakSchema,
} from "@/shared/api/schemas/metrics";
import { metricsQueryKeys } from "./metricsQueryKeys";

interface DateRange {
  date_from: string;
  date_to: string;
  /** Org + member scoping — the "Członek" filter. Omit both for "just me"
   * (the historical, still-default behaviour on the standalone /metrics
   * page, which has no org context). */
  organizationId?: string;
  memberUserId?: string;
  /** Gates the date-range queries (not `streaks`, which isn't windowed).
   * Defaults to `true` — pass `false` while the caller's window is still
   * resolving (e.g. the dashboard's shared sprint period) so a fetch
   * doesn't fire against a meaningless placeholder range. */
  enabled?: boolean;
}

export function useMetricsQueries({
  date_from,
  date_to,
  organizationId,
  memberUserId,
  enabled = true,
}: DateRange) {
  const scope = {
    ...(organizationId ? { organization_id: organizationId } : {}),
    ...(memberUserId ? { member_user_id: memberUserId } : {}),
  };
  const params = { date_from, date_to, ...scope };

  const velocity = useQuery({
    queryKey: [...metricsQueryKeys.all, "velocity", params],
    enabled,
    queryFn: () =>
      apiClient
        .get("/metrics/velocity", { params })
        .then((r) => VelocitySchema.parse(r.data)),
  });

  const timeTracking = useQuery({
    queryKey: [...metricsQueryKeys.all, "time-tracking", params],
    enabled,
    queryFn: () =>
      apiClient
        .get("/metrics/time-tracking", { params })
        .then((r) => TimeTrackingSchema.parse(r.data)),
  });

  const completionRate = useQuery({
    queryKey: [...metricsQueryKeys.all, "completion-rate", params],
    enabled,
    queryFn: () =>
      apiClient
        .get("/metrics/completion-rate", { params })
        .then((r) => CompletionRateSchema.parse(r.data)),
  });

  const estimationAccuracy = useQuery({
    queryKey: [...metricsQueryKeys.all, "estimation-accuracy", params],
    enabled,
    queryFn: () =>
      apiClient
        .get("/metrics/estimation-accuracy", { params })
        .then((r) => EstimationAccuracySchema.parse(r.data)),
  });

  const streaks = useQuery({
    queryKey: [...metricsQueryKeys.all, "streaks", scope],
    queryFn: () =>
      apiClient
        .get("/metrics/streaks", { params: scope })
        .then((r) => StreakSchema.parse(r.data)),
  });

  return { velocity, timeTracking, completionRate, estimationAccuracy, streaks };
}
