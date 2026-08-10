// Shared recharts layout/style defaults so every chart doesn't re-hardcode
// margins, axis styling, and grid styling separately.

// `left: -16` reclaims the ~60px recharts reserves by default for the
// y-axis label gutter — without it every chart looks cramped.
export const CHART_MARGIN = { top: 8, right: 8, bottom: 0, left: -16 };

export function axisProps(color: string): {
  stroke: string;
  tickLine: false;
  axisLine: false;
  tick: { fontSize: number; fill: string };
} {
  return {
    stroke: color,
    tickLine: false,
    axisLine: false,
    tick: { fontSize: 11, fill: color },
  };
}

export function gridProps(color: string): {
  stroke: string;
  strokeDasharray: string;
  vertical: boolean;
} {
  // Horizontal-only gridlines for time series; part-to-whole charts skip
  // the grid entirely by simply not rendering <CartesianGrid>.
  return { stroke: color, strokeDasharray: "0", vertical: false };
}
