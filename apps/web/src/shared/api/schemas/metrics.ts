import { z } from "zod";

export const MetricValueSchema = z.object({
  value: z.number(),
  prev_value: z.number(),
  delta_pct: z.number().nullable(),
});

export const SummarySchema = z.object({
  period_from: z.string(),
  period_to: z.string(),
  tasks_completed: MetricValueSchema,
  active_hours: MetricValueSchema,
});

export const WeeklyVelocityPointSchema = z.object({
  week_start: z.string(),
  tasks_completed: z.number(),
});

export const VelocitySchema = z.object({
  period_from: z.string(),
  period_to: z.string(),
  total_done: z.number(),
  weeks: z.number(),
  average_per_week: z.number(),
  trend_pct: z.number().nullable(),
  weekly: z.array(WeeklyVelocityPointSchema),
});

export const DailyHoursSchema = z.object({
  day: z.string(),
  hours: z.number(),
});

export const TimeTrackingSchema = z.object({
  period_from: z.string(),
  period_to: z.string(),
  total_hours: z.number(),
  daily: z.array(DailyHoursSchema),
});

export const CompletionRateSchema = z.object({
  period_from: z.string(),
  period_to: z.string(),
  done: z.number(),
  cancelled: z.number(),
  open: z.number(),
  completion_rate: z.number(),
});

export const EstimationAccuracySchema = z.object({
  period_from: z.string(),
  period_to: z.string(),
  sample_size: z.number(),
  average_ratio: z.number().nullable(),
  accurate_count: z.number(),
  over_estimated_count: z.number(),
  under_estimated_count: z.number(),
});

export const StreakSchema = z.object({
  current_streak: z.number(),
  longest_streak: z.number(),
});

export const PRDashboardSchema = z.object({
  stale_pr_count: z.number(),
  time_to_first_review: z.number().nullable(),
  review_velocity: z.number().nullable(),
  weekly_throughput: z.number(),
  review_ratio: z.number().nullable(),
});

export const PRDashboardMemberSchema = z.object({
  user_id: z.string(),
  display_name: z.string(),
  github_login: z.string().nullable(),
});

export const PRDashboardMembersSchema = z.object({
  data: z.array(PRDashboardMemberSchema),
});

export const PRTrendPointSchema = z.object({
  week_start: z.string(),
  opened: z.number(),
  merged: z.number(),
  avg_time_to_first_review_h: z.number().nullable(),
});

export const PRTrendsSchema = z.object({
  period_from: z.string(),
  period_to: z.string(),
  weekly: z.array(PRTrendPointSchema),
});

export const MetricTrendPointSchema = z.object({
  week_start: z.string(),
  value: z.number().nullable(),
});

export const MetricTrendSeriesSchema = z.object({
  metric_key: z.string(),
  points: z.array(MetricTrendPointSchema),
});

export const MetricTrendsSchema = z.object({
  period_from: z.string(),
  period_to: z.string(),
  weeks: z.number(),
  series: z.array(MetricTrendSeriesSchema),
});

export const CycleTimeStageSchema = z.object({
  status: z.string(),
  average_hours: z.number(),
  sample_size: z.number(),
});

export const StuckTaskSchema = z.object({
  task_id: z.string(),
  title: z.string(),
  status: z.string(),
  hours_in_status: z.number(),
});

export const CycleTimeSchema = z.object({
  project_id: z.string(),
  stages: z.array(CycleTimeStageSchema),
  stuck: z.array(StuckTaskSchema),
});

export type MetricValue = z.infer<typeof MetricValueSchema>;
export type Summary = z.infer<typeof SummarySchema>;
export type WeeklyVelocityPoint = z.infer<typeof WeeklyVelocityPointSchema>;
export type Velocity = z.infer<typeof VelocitySchema>;
export type DailyHours = z.infer<typeof DailyHoursSchema>;
export type TimeTracking = z.infer<typeof TimeTrackingSchema>;
export type CompletionRate = z.infer<typeof CompletionRateSchema>;
export type EstimationAccuracy = z.infer<typeof EstimationAccuracySchema>;
export type Streak = z.infer<typeof StreakSchema>;
export type PRDashboard = z.infer<typeof PRDashboardSchema>;
export type PRDashboardMember = z.infer<typeof PRDashboardMemberSchema>;
export type PRDashboardMembers = z.infer<typeof PRDashboardMembersSchema>;
export type PRTrendPoint = z.infer<typeof PRTrendPointSchema>;
export type PRTrends = z.infer<typeof PRTrendsSchema>;
export type MetricTrendPoint = z.infer<typeof MetricTrendPointSchema>;
export type MetricTrendSeries = z.infer<typeof MetricTrendSeriesSchema>;
export type MetricTrends = z.infer<typeof MetricTrendsSchema>;
export type CycleTimeStage = z.infer<typeof CycleTimeStageSchema>;
export type StuckTask = z.infer<typeof StuckTaskSchema>;
export type CycleTime = z.infer<typeof CycleTimeSchema>;
