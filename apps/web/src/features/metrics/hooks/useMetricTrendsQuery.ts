import { useQuery } from "@tanstack/react-query";
import { apiClient } from "@/shared/api/client";
import { MetricTrendsSchema } from "@/shared/api/schemas/metrics";
import { metricsQueryKeys } from "./metricsQueryKeys";

export function useMetricTrendsQuery(weeks: number) {
  return useQuery({
    queryKey: [...metricsQueryKeys.all, "trends", weeks],
    queryFn: () =>
      apiClient
        .get("/metrics/trends", { params: { weeks } })
        .then((r) => MetricTrendsSchema.parse(r.data)),
  });
}
