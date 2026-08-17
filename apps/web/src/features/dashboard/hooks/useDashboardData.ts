import { useQuery } from "@tanstack/react-query";
import { apiClient } from "@/shared/api/client";
import { SummarySchema, VelocitySchema } from "@/shared/api/schemas/metrics";
import { daysAgoLocal, todayLocal } from "@/shared/lib/localDate";
import { metricsQueryKeys } from "@/features/metrics/hooks/metricsQueryKeys";

export function useDashboardData() {
  const date_to = todayLocal();
  const date_from = daysAgoLocal(30);
  const params = { date_from, date_to };

  const { data: summary, isLoading: summaryLoading } = useQuery({
    queryKey: [...metricsQueryKeys.all, "summary", params],
    queryFn: () =>
      apiClient
        .get("/metrics/summary", { params })
        .then((r) => SummarySchema.parse(r.data)),
  });

  const { data: velocity, isLoading: velocityLoading } = useQuery({
    queryKey: [...metricsQueryKeys.all, "velocity", params],
    queryFn: () =>
      apiClient
        .get("/metrics/velocity", { params })
        .then((r) => VelocitySchema.parse(r.data)),
  });

  return {
    summary,
    velocity,
    isLoading: summaryLoading || velocityLoading,
  };
}
