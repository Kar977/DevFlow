import { useQuery } from "@tanstack/react-query";
import { apiClient } from "@/shared/api/client";

export interface PRDashboard {
  stale_pr_count: number;
  time_to_first_review: number | null;
  review_velocity: number | null;
  weekly_throughput: number;
  review_ratio: number | null;
}

export function usePRDashboardQuery() {
  return useQuery({
    queryKey: ["metrics", "pr-dashboard"],
    queryFn: () =>
      apiClient.get("/metrics/pr-dashboard").then((r) => r.data as PRDashboard),
  });
}
