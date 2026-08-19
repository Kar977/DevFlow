import { Card, CardContent, CardHeader, CardTitle } from "@/shared/ui";

interface Props {
  title: string;
  /** `null` means "no data to compute" — rendered as "—", never "0", so a
   * genuinely empty dataset can't be mistaken for a perfect score. */
  value: number | null;
  delta?: number;
  /** Tooltip (native `title` attribute) explaining what the tile measures
   * and its window — most PR-flow tiles have no other way to show this. */
  hint?: string;
  /** Formats `value` for display, e.g. `formatHours` / `formatPercent` from
   * `shared/charts/format.ts`. Defaults to a plain string conversion. */
  formatValue?: (value: number) => string;
  /** Set for tiles where a *lower* value is the improvement (e.g. wait
   * times) — flips which delta sign renders green vs red. */
  invertDelta?: boolean;
}

export function KpiCard({
  title,
  value,
  delta,
  hint,
  formatValue,
  invertDelta = false,
}: Props) {
  const hasDelta = delta !== undefined;
  const isImprovement = hasDelta && (invertDelta ? delta <= 0 : delta >= 0);
  const display =
    value === null ? "—" : formatValue ? formatValue(value) : String(value);

  return (
    <Card title={hint}>
      <CardHeader>
        <CardTitle className="text-sm font-medium text-muted-foreground">{title}</CardTitle>
      </CardHeader>
      <CardContent>
        <div className="text-2xl font-bold">{display}</div>
        {hasDelta && (
          <p className={isImprovement ? "text-green-500 text-sm" : "text-red-500 text-sm"}>
            {delta >= 0 ? "+" : ""}
            {delta.toFixed(1)}%
          </p>
        )}
      </CardContent>
    </Card>
  );
}
