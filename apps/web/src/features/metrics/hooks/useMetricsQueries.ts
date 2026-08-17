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
}

export function useMetricsQueries({ date_from, date_to }: DateRange) {
  const params = { date_from, date_to };

  const velocity = useQuery({
    queryKey: [...metricsQueryKeys.all, "velocity", params],
    queryFn: () =>
      apiClient
        .get("/metrics/velocity", { params })
        .then((r) => VelocitySchema.parse(r.data)),
  });

  const timeTracking = useQuery({
    queryKey: [...metricsQueryKeys.all, "time-tracking", params],
    queryFn: () =>
      apiClient
        .get("/metrics/time-tracking", { params })
        .then((r) => TimeTrackingSchema.parse(r.data)),
  });

  const completionRate = useQuery({
    queryKey: [...metricsQueryKeys.all, "completion-rate", params],
    queryFn: () =>
      apiClient
        .get("/metrics/completion-rate", { params })
        .then((r) => CompletionRateSchema.parse(r.data)),
  });

  const estimationAccuracy = useQuery({
    queryKey: [...metricsQueryKeys.all, "estimation-accuracy", params],
    queryFn: () =>
      apiClient
        .get("/metrics/estimation-accuracy", { params })
        .then((r) => EstimationAccuracySchema.parse(r.data)),
  });

  const streaks = useQuery({
    queryKey: [...metricsQueryKeys.all, "streaks"],
    queryFn: () =>
      apiClient.get("/metrics/streaks").then((r) => StreakSchema.parse(r.data)),
  });

  return { velocity, timeTracking, completionRate, estimationAccuracy, streaks };
}
