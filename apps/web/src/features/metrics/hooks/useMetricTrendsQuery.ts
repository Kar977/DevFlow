import { useQuery } from "@tanstack/react-query";
import { apiClient } from "@/shared/api/client";
import { MetricTrendsSchema } from "@/shared/api/schemas/metrics";

export function useMetricTrendsQuery(weeks: number) {
  return useQuery({
    queryKey: ["metrics", "trends", weeks],
    queryFn: () =>
      apiClient
        .get("/metrics/trends", { params: { weeks } })
        .then((r) => MetricTrendsSchema.parse(r.data)),
  });
}
