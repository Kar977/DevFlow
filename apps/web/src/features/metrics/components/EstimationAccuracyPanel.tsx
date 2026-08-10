import { BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer } from "recharts";
import { ChartCard, ChartTooltip, useChartPalette } from "@/shared/charts";
import type { EstimationAccuracy } from "@/shared/types";

interface Props {
  data?: EstimationAccuracy;
  isLoading?: boolean;
}

// Three ratio buckets are ordered positions on one continuous axis
// (ratio <0.8 → 0.8-1.2 → >1.2) with "accurate" as a meaningful neutral
// midpoint — this is diverging, not categorical. A single stacked bar
// (over-left, accurate-middle, under-right) carries that ordering
// spatially; colors are borrowed from the validated categorical set
// (blue ↔ neutral ↔ orange) rather than an unvalidated diverging ramp.
export function EstimationAccuracyPanel({ data, isLoading }: Props) {
  const palette = useChartPalette();
  const isEmpty = !data || data.sample_size === 0;
  const avgDeltaPct =
    data?.average_ratio != null ? (data.average_ratio - 1) * 100 : null;

  const row = data
    ? [
        {
          name: "Zadania",
          over: data.over_estimated_count,
          accurate: data.accurate_count,
          under: data.under_estimated_count,
        },
      ]
    : [];

  return (
    <ChartCard
      title="Dokładność estymacji"
      subtitle="przeszacowane ← dokładne → niedoszacowane"
      isLoading={isLoading}
      isEmpty={isEmpty}
      series={[
        { label: "Przeszacowane", color: palette.estimation.over },
        { label: "Dokładne", color: palette.estimation.accurate },
        { label: "Niedoszacowane", color: palette.estimation.under },
      ]}
    >
      {data && (
        <div className="space-y-3">
          {avgDeltaPct !== null && (
            <div>
              <p className="text-sm text-muted-foreground">
                Śr. odchylenie od estymacji
              </p>
              <p className="text-2xl font-bold">
                {avgDeltaPct >= 0 ? "+" : ""}
                {avgDeltaPct.toFixed(1)}%
              </p>
            </div>
          )}
          <ResponsiveContainer width="100%" height={48}>
            <BarChart
              data={row}
              layout="vertical"
              margin={{ top: 0, right: 0, bottom: 0, left: 0 }}
            >
              <XAxis type="number" domain={[0, data.sample_size]} hide />
              <YAxis type="category" dataKey="name" hide />
              <Tooltip content={<ChartTooltip />} />
              <Bar
                dataKey="over"
                stackId="a"
                name="Przeszacowane"
                fill={palette.estimation.over}
                radius={[4, 0, 0, 4]}
              />
              <Bar
                dataKey="accurate"
                stackId="a"
                name="Dokładne"
                fill={palette.estimation.accurate}
              />
              <Bar
                dataKey="under"
                stackId="a"
                name="Niedoszacowane"
                fill={palette.estimation.under}
                radius={[0, 4, 4, 0]}
              />
            </BarChart>
          </ResponsiveContainer>
        </div>
      )}
    </ChartCard>
  );
}
