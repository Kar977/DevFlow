import { useQuery } from "@tanstack/react-query";
import { apiClient } from "@/shared/api/client";
import {
  VelocitySchema,
  TimeTrackingSchema,
  CompletionRateSchema,
  EstimationAccuracySchema,
  StreakSchema,
} from "@/shared/api/schemas/metrics";

interface DateRange {
  date_from: string;
  date_to: string;
}

export function useMetricsQueries({ date_from, date_to }: DateRange) {
  const params = { date_from, date_to };

  const velocity = useQuery({
    queryKey: ["metrics", "velocity", params],
    queryFn: () =>
      apiClient
        .get("/metrics/velocity", { params })
        .then((r) => VelocitySchema.parse(r.data)),
  });

  const timeTracking = useQuery({
    queryKey: ["metrics", "time-tracking", params],
    queryFn: () =>
      apiClient
        .get("/metrics/time-tracking", { params })
        .then((r) => TimeTrackingSchema.parse(r.data)),
  });

  const completionRate = useQuery({
    queryKey: ["metrics", "completion-rate", params],
    queryFn: () =>
      apiClient
        .get("/metrics/completion-rate", { params })
        .then((r) => CompletionRateSchema.parse(r.data)),
  });

  const estimationAccuracy = useQuery({
    queryKey: ["metrics", "estimation-accuracy", params],
    queryFn: () =>
      apiClient
        .get("/metrics/estimation-accuracy", { params })
        .then((r) => EstimationAccuracySchema.parse(r.data)),
  });

  const streaks = useQuery({
    queryKey: ["metrics", "streaks"],
    queryFn: () =>
      apiClient.get("/metrics/streaks").then((r) => StreakSchema.parse(r.data)),
  });

  return { velocity, timeTracking, completionRate, estimationAccuracy, streaks };
}
