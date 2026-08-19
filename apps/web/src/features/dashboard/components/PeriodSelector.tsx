import { DateRangePicker } from "@/features/metrics/components/DateRangePicker";
import type { DashboardWindow, PeriodMode } from "../lib/period";

interface Props {
  mode: PeriodMode;
  onModeChange: (mode: PeriodMode) => void;
  customRange: DashboardWindow;
  onCustomRangeChange: (range: DashboardWindow) => void;
  /** The window actually in effect, for the "Okres: ..." readout — may
   * still be undefined for a moment while the sprint series is loading. */
  effectiveWindow: DashboardWindow | undefined;
  /** False when the org has no sprint cadence configured — the "Bieżący
   * sprint" / "Poprzedni sprint" options are disabled in that case, since
   * there's nothing for them to resolve to. */
  sprintsAvailable: boolean;
}

/**
 * Shared period control for the whole dashboard (both the "Flow" and
 * "Produktywność" tabs) — previously each tab picked its own window, so
 * they could (and did) show metrics for two different periods at once.
 */
export function PeriodSelector({
  mode,
  onModeChange,
  customRange,
  onCustomRangeChange,
  effectiveWindow,
  sprintsAvailable,
}: Props) {
  return (
    <div className="flex flex-wrap items-center gap-4">
      <div className="flex items-center gap-2">
        <label htmlFor="dashboard-period-select" className="text-sm text-muted-foreground">
          Okres:
        </label>
        <select
          id="dashboard-period-select"
          value={mode}
          onChange={(e) => onModeChange(e.target.value as PeriodMode)}
          className="rounded border border-border bg-background px-3 py-1.5 text-sm"
        >
          <option value="current" disabled={!sprintsAvailable}>
            Bieżący sprint
          </option>
          <option value="previous" disabled={!sprintsAvailable}>
            Poprzedni sprint
          </option>
          <option value="custom">Własny zakres</option>
        </select>
      </div>

      {!sprintsAvailable && mode !== "custom" && (
        <p className="text-xs text-muted-foreground">
          Kadencja sprintu nie jest skonfigurowana — ustaw ją w Ustawieniach
          organizacji, zakładka „Sprinty”.
        </p>
      )}

      {mode === "custom" && (
        <DateRangePicker
          initialDateFrom={customRange.date_from}
          initialDateTo={customRange.date_to}
          onApply={onCustomRangeChange}
        />
      )}

      {effectiveWindow && (
        <p className="text-xs text-muted-foreground">
          Okres: {effectiveWindow.date_from} – {effectiveWindow.date_to}
        </p>
      )}
    </div>
  );
}
