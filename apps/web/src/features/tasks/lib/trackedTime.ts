/** Formats a duration in seconds as "Xh Ym" (or just "Ym" under an hour). */
export function formatTrackedTime(totalSeconds: number): string {
  const totalMinutes = Math.floor(totalSeconds / 60);
  const hours = Math.floor(totalMinutes / 60);
  const minutes = totalMinutes % 60;
  if (hours > 0) {
    return `${hours}h ${minutes}m`;
  }
  return `${minutes}m`;
}

/**
 * Formats a duration in seconds as a running clock: "M:SS" under an hour,
 * "H:MM:SS" at or above. Used for live timer displays (sidebar, timer
 * button) — unlike `formatTrackedTime`, which is for aggregate totals, this
 * must not silently overflow minutes past 59 for a multi-hour session
 * (e.g. a forgotten timer would otherwise render as "360:12").
 */
export function formatElapsed(totalSeconds: number): string {
  const hours = Math.floor(totalSeconds / 3600);
  const minutes = Math.floor((totalSeconds % 3600) / 60);
  const seconds = totalSeconds % 60;
  const paddedSeconds = String(seconds).padStart(2, "0");
  if (hours > 0) {
    return `${hours}:${String(minutes).padStart(2, "0")}:${paddedSeconds}`;
  }
  return `${minutes}:${paddedSeconds}`;
}
