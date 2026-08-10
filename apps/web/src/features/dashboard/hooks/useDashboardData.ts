import { useQuery } from "@tanstack/react-query";
import { apiClient } from "@/shared/api/client";
import { SummarySchema, VelocitySchema } from "@/shared/api/schemas/metrics";

function daysAgo(n: number): string {
  const d = new Date();
  d.setDate(d.getDate() - n);
  return d.toISOString().split("T")[0]!;
}

export function useDashboardData() {
  const date_to = new Date().toISOString().split("T")[0]!;
  const date_from = daysAgo(30);
  const params = { date_from, date_to };

  const { data: summary, isLoading: summaryLoading } = useQuery({
    queryKey: ["metrics", "summary", params],
    queryFn: () =>
      apiClient
        .get("/metrics/summary", { params })
        .then((r) => SummarySchema.parse(r.data)),
  });

  const { data: velocity, isLoading: velocityLoading } = useQuery({
    queryKey: ["metrics", "velocity", params],
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
