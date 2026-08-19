import {
  BarChart,
  Bar,
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

// Two series (opened, merged) — kept on the two contrast-safe slots (blue,
// orange). Aqua would read intuitively as "good/merged" but fails 3:1 on
// the card surface; blue+orange keeps both series above the relief-rule
// threshold without relying on the legend alone.
export function PRThroughputChart({ data, isLoading }: Props) {
  const palette = useChartPalette();

  return (
    <ChartCard
      title="Przepływ PR — otwarte vs zmergowane"
      isLoading={isLoading}
      isEmpty={!data}
      series={[
        { label: "Otwarte", color: palette.series.primary },
        { label: "Zmergowane", color: palette.series.secondary },
      ]}
    >
      <ResponsiveContainer width="100%" height={200}>
        <BarChart data={data?.weekly ?? []} margin={CHART_MARGIN}>
          <CartesianGrid {...gridProps(palette.chrome.grid)} />
          <XAxis
            dataKey="week_start"
            tickFormatter={formatWeekLabel}
            {...axisProps(palette.chrome.axis)}
          />
          <YAxis allowDecimals={false} {...axisProps(palette.chrome.axis)} />
          <Tooltip content={<ChartTooltip labelFormatter={formatWeekLabel} />} />
          <Bar
            dataKey="opened"
            name="Otwarte"
            fill={palette.series.primary}
            radius={[2, 2, 0, 0]}
          />
          <Bar
            dataKey="merged"
            name="Zmergowane"
            fill={palette.series.secondary}
            radius={[2, 2, 0, 0]}
          />
        </BarChart>
      </ResponsiveContainer>
    </ChartCard>
  );
}
