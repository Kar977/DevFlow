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
import type { PRTrends } from "@/shared/types";

interface Props {
  data?: PRTrends;
  isLoading?: boolean;
}

export function ReviewLatencyChart({ data, isLoading }: Props) {
  const palette = useChartPalette();
  const isEmpty =
    !data || data.weekly.every((p) => p.avg_time_to_first_review_h === null);

  return (
    <ChartCard
      title="Czas do 1. review (śr. h)"
      subtitle="ostatnie tygodnie mogą być niepełne — PR-y jeszcze bez review są pominięte"
      isLoading={isLoading}
      isEmpty={isEmpty}
    >
      <ResponsiveContainer width="100%" height={200}>
        <LineChart data={data?.weekly ?? []} margin={CHART_MARGIN}>
          <CartesianGrid {...gridProps(palette.chrome.grid)} />
          <XAxis
            dataKey="week_start"
            tickFormatter={formatWeekLabel}
            {...axisProps(palette.chrome.axis)}
          />
          <YAxis {...axisProps(palette.chrome.axis)} />
          <Tooltip content={<ChartTooltip labelFormatter={formatWeekLabel} />} />
          <Line
            type="monotone"
            dataKey="avg_time_to_first_review_h"
            name="Godziny"
            stroke={palette.series.primary}
            strokeWidth={2}
            connectNulls={false}
            dot={{ r: 3, fill: palette.series.primary }}
          />
        </LineChart>
      </ResponsiveContainer>
    </ChartCard>
  );
}
