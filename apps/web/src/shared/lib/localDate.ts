/**
 * Local-calendar-date helpers for date-range params.
 *
 * `Date.prototype.toISOString()` always renders in UTC, so
 * `new Date().toISOString().split("T")[0]` names the wrong day for anyone
 * west of UTC before ~midnight-plus-offset local time (e.g. before 02:00 in
 * CEST) — "today" becomes yesterday's date on the wire. These helpers build
 * the `YYYY-MM-DD` string from the local calendar fields instead, so what
 * the user sees as "today" is what gets sent as `date_to`.
 */

function pad(n: number): string {
  return String(n).padStart(2, "0");
}

export function toLocalDateString(d: Date): string {
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}`;
}

export function todayLocal(): string {
  return toLocalDateString(new Date());
}

export function daysAgoLocal(n: number): string {
  const d = new Date();
  d.setDate(d.getDate() - n);
  return toLocalDateString(d);
}
