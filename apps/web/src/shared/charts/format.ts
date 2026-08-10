// Pure formatting helpers for chart axis ticks and labels — kept separate
// from components so they can be unit-tested without mounting recharts.

/** "2026-08-03" → "03.08" (Polish day.month, matches app-wide date style). */
export function formatWeekLabel(weekStart: string): string {
  return formatDayLabel(weekStart);
}

/** "2026-08-03" → "03.08". */
export function formatDayLabel(day: string): string {
  const date = new Date(day);
  if (Number.isNaN(date.getTime())) {
    return day;
  }
  const dd = String(date.getUTCDate()).padStart(2, "0");
  const mm = String(date.getUTCMonth() + 1).padStart(2, "0");
  return `${dd}.${mm}`;
}

/** 4.5 → "4.5 h" */
export function formatHours(hours: number): string {
  return `${hours.toFixed(1)} h`;
}

/** 0.723 → "72%" (backend `completion_rate` is already 0–100, not 0–1). */
export function formatPercent(value: number): string {
  return `${Math.round(value)}%`;
}
