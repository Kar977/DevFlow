import { useState } from "react";
import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
} from "recharts";
import {
  ChartCard,
  ChartTooltip,
  useChartPalette,
  CHART_MARGIN,
  axisProps,
  gridProps,
  formatWeekLabel,
} from "@/shared/charts";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/shared/ui";
import type { MetricTrends } from "@/shared/types";

// The 4 productivity metrics captured in metric_snapshots (backend
// USER_METRIC_KEYS) mix units (count, hours, percent, ratio) — plotting all
// 4 as lines on one shared Y-axis would make the smaller series unreadable.
// A metric selector (one line at a time) avoids that instead of a
// multi-axis chart.
const METRIC_LABELS: Record<string, string> = {
  tasks_completed: "Ukończone zadania",
  active_hours: "Aktywne godziny",
  completion_rate: "Wskaźnik ukończenia (%)",
  estimation_ratio: "Trafność estymacji (rzeczywisty / szacowany czas)",
};
const DEFAULT_METRIC_KEY = "tasks_completed";

const WEEKS_OPTIONS = [12, 26, 52] as const;

interface Props {
  data?: MetricTrends;
  isLoading?: boolean;
  weeks: number;
  onWeeksChange: (weeks: number) => void;
}

export function MetricTrendsPanel({ data, isLoading, weeks, onWeeksChange }: Props) {
  const palette = useChartPalette();
  const [metricKey, setMetricKey] = useState<string>(DEFAULT_METRIC_KEY);

  const points = data?.series.find((s) => s.metric_key === metricKey)?.points ?? [];
  const isEmpty = !data || points.every((p) => p.value === null);

  return (
    <div className="space-y-3">
      <div className="flex flex-wrap items-center gap-3">
        <Select value={metricKey} onValueChange={setMetricKey}>
          <SelectTrigger className="w-64">
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            {Object.entries(METRIC_LABELS).map(([key, label]) => (
              <SelectItem key={key} value={key}>
                {label}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
        <Select
          value={String(weeks)}
          onValueChange={(value) => onWeeksChange(Number(value))}
        >
          <SelectTrigger className="w-28">
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            {WEEKS_OPTIONS.map((option) => (
              <SelectItem key={option} value={String(option)}>
                {option} tyg.
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
      </div>

      <ChartCard
        title="Długoterminowy trend metryki"
        subtitle="niezależny od zakresu dat wybranego powyżej — pełna historia tygodniowa"
        isLoading={isLoading}
        isEmpty={isEmpty}
      >
        <ResponsiveContainer width="100%" height={200}>
          <LineChart data={points} margin={CHART_MARGIN}>
            <CartesianGrid {...gridProps(palette.chrome.grid)} />
            <XAxis
              dataKey="week_start"
              tickFormatter={formatWeekLabel}
              {...axisProps(palette.chrome.axis)}
            />
            <YAxis {...axisProps(palette.chrome.axis)} />
            <Tooltip content={<ChartTooltip />} />
            <Line
              type="monotone"
              dataKey="value"
              name={METRIC_LABELS[metricKey] ?? metricKey}
              stroke={palette.series.primary}
              strokeWidth={2}
              connectNulls={false}
              dot={{ r: 3, fill: palette.series.primary }}
            />
          </LineChart>
        </ResponsiveContainer>
      </ChartCard>
    </div>
  );
}
