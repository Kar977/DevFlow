import {
  AreaChart,
  Area,
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
  formatDayLabel,
} from "@/shared/charts";
import type { TimeTracking } from "@/shared/types";

interface Props {
  data?: TimeTracking;
  isLoading?: boolean;
}

export function TimeTrackingPanel({ data, isLoading }: Props) {
  const palette = useChartPalette();
  const isEmpty = !data || data.daily.length === 0;

  return (
    <ChartCard title="Godziny dziennie" isLoading={isLoading} isEmpty={isEmpty}>
      <ResponsiveContainer width="100%" height={160}>
        <AreaChart data={data?.daily ?? []} margin={CHART_MARGIN}>
          <CartesianGrid {...gridProps(palette.chrome.grid)} />
          <XAxis
            dataKey="day"
            tickFormatter={formatDayLabel}
            {...axisProps(palette.chrome.axis)}
          />
          <YAxis {...axisProps(palette.chrome.axis)} />
          <Tooltip content={<ChartTooltip />} />
          <Area
            type="monotone"
            dataKey="hours"
            name="Godziny"
            stroke={palette.series.primary}
            fill={palette.series.primary}
            fillOpacity={0.12}
          />
        </AreaChart>
      </ResponsiveContainer>
    </ChartCard>
  );
}
