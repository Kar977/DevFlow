import { BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer } from "recharts";
import {
  ChartCard,
  ChartTooltip,
  useChartPalette,
  CHART_MARGIN,
  axisProps,
  gridProps,
  formatHours,
} from "@/shared/charts";
import { Badge } from "@/shared/ui";
import { taskStatusLabel } from "@/features/tasks/lib/taskStatusLabels";
import type { CycleTime } from "@/shared/types";

interface Props {
  data?: CycleTime;
  isLoading?: boolean;
}

/**
 * Average time-in-status from `task_status_changes`, plus the tasks
 * currently sitting longest in a non-terminal status — the practical
 * "what's a bottleneck right now" companion the averages alone can't show
 * (a status with zero completed transitions today can still be silently
 * hiding a stuck task).
 */
export function CycleTimePanel({ data, isLoading }: Props) {
  const palette = useChartPalette();
  const isEmpty = !data || (data.stages.length === 0 && data.stuck.length === 0);

  const rows = (data?.stages ?? []).map((stage) => ({
    statusLabel: taskStatusLabel(stage.status),
    average_hours: stage.average_hours,
    sample_size: stage.sample_size,
  }));

  return (
    <ChartCard
      title="Cycle time per etap"
      subtitle="Średni czas między wejściem a wyjściem ze statusu."
      isLoading={isLoading}
      isEmpty={isEmpty}
      emptyLabel="Brak historii statusów do policzenia."
    >
      {rows.length > 0 && (
        <ResponsiveContainer width="100%" height={Math.max(120, rows.length * 40)}>
          <BarChart
            data={rows}
            layout="vertical"
            margin={CHART_MARGIN}
          >
            <CartesianGrid {...gridProps(palette.chrome.grid)} horizontal={false} />
            <XAxis
              type="number"
              tickFormatter={formatHours}
              {...axisProps(palette.chrome.axis)}
            />
            <YAxis
              type="category"
              dataKey="statusLabel"
              width={90}
              {...axisProps(palette.chrome.axis)}
            />
            <Tooltip content={<ChartTooltip />} />
            <Bar
              dataKey="average_hours"
              name="Śr. czas"
              fill={palette.series.primary}
              radius={[0, 2, 2, 0]}
            />
          </BarChart>
        </ResponsiveContainer>
      )}

      {data && data.stuck.length > 0 && (
        <div className="mt-4 flex flex-col gap-2">
          <p className="text-xs font-medium text-muted-foreground">
            Najdłużej bez zmiany
          </p>
          <ul className="flex flex-col gap-1.5">
            {data.stuck.map((task) => (
              <li
                key={task.task_id}
                className="flex items-center justify-between gap-2 text-sm"
              >
                <span className="truncate">{task.title}</span>
                <span className="flex shrink-0 items-center gap-2">
                  <Badge variant="secondary">{taskStatusLabel(task.status)}</Badge>
                  <span className="text-muted-foreground">
                    {formatHours(task.hours_in_status)}
                  </span>
                </span>
              </li>
            ))}
          </ul>
        </div>
      )}
    </ChartCard>
  );
}
