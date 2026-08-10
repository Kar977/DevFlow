import { BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer } from "recharts";
import {
  ChartCard,
  ChartTooltip,
  useChartPalette,
  formatPercent,
} from "@/shared/charts";
import type { CompletionRate } from "@/shared/types";

interface Props {
  data?: CompletionRate;
  isLoading?: boolean;
}

export function CompletionRatePanel({ data, isLoading }: Props) {
  const palette = useChartPalette();
  const total = data ? data.done + data.cancelled + data.open : 0;
  const isEmpty = !data || total === 0;

  const row = data
    ? [{ name: "Zadania", done: data.done, open: data.open, cancelled: data.cancelled }]
    : [];

  return (
    <ChartCard
      title="Completion rate"
      isLoading={isLoading}
      isEmpty={isEmpty}
      series={[
        { label: "Ukończone", color: palette.completion.done },
        { label: "Otwarte", color: palette.completion.open },
        { label: "Anulowane", color: palette.completion.cancelled },
      ]}
    >
      {data && (
        <div className="flex items-center gap-4">
          {/* completion_rate is already 0-100 from the backend — no *100 here. */}
          <div className="text-3xl font-bold">{formatPercent(data.completion_rate)}</div>
          <ResponsiveContainer width="100%" height={48}>
            <BarChart data={row} layout="vertical" margin={{ top: 0, right: 0, bottom: 0, left: 0 }}>
              <XAxis type="number" domain={[0, total]} hide />
              <YAxis type="category" dataKey="name" hide />
              <Tooltip content={<ChartTooltip />} />
              <Bar
                dataKey="done"
                stackId="a"
                name="Ukończone"
                fill={palette.completion.done}
                radius={[4, 0, 0, 4]}
              />
              <Bar dataKey="open" stackId="a" name="Otwarte" fill={palette.completion.open} />
              <Bar
                dataKey="cancelled"
                stackId="a"
                name="Anulowane"
                fill={palette.completion.cancelled}
                radius={[0, 4, 4, 0]}
              />
            </BarChart>
          </ResponsiveContainer>
        </div>
      )}
    </ChartCard>
  );
}
