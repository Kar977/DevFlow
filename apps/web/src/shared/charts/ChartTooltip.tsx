import type { ReactNode } from "react";
import type { TooltipProps } from "recharts";
import type {
  NameType,
  ValueType,
} from "recharts/types/component/DefaultTooltipContent";

interface Props extends TooltipProps<ValueType, NameType> {
  /** Formats the header (`label`) — e.g. `formatWeekLabel` so the tooltip's
   * "2026-08-03" matches the axis's own "03.08" instead of showing the raw
   * ISO date. Defaults to the identity (today's behaviour) since not every
   * chart's label is a date — `CycleTimePanel`'s is a task status name. */
  labelFormatter?: (label: string) => ReactNode;
}

/** Styled `content` renderer for recharts `<Tooltip content={ChartTooltip} />`. */
export function ChartTooltip({ active, payload, label, labelFormatter }: Props) {
  if (!active || !payload || payload.length === 0) {
    return null;
  }
  return (
    <div className="rounded-md border border-border bg-card px-3 py-2 text-xs shadow-sm">
      {label !== undefined && (
        <div className="mb-1 font-medium text-foreground">
          {labelFormatter ? labelFormatter(label) : label}
        </div>
      )}
      {payload.map((entry) => (
        <div
          key={String(entry.dataKey)}
          className="flex items-center gap-1.5 text-muted-foreground"
        >
          <span
            className="h-2 w-2 rounded-full"
            style={{ backgroundColor: entry.color }}
          />
          <span>
            {entry.name}: {entry.value}
          </span>
        </div>
      ))}
    </div>
  );
}
