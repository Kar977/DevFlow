/** Polish plural forms for "zadanie" (task), used by the overdue-tasks banner. */
export function pluralizeTasks(count: number): string {
  if (count === 1) return "zadanie";
  const lastDigit = count % 10;
  const lastTwoDigits = count % 100;
  if (lastDigit >= 2 && lastDigit <= 4 && !(lastTwoDigits >= 12 && lastTwoDigits <= 14)) {
    return "zadania";
  }
  return "zadań";
}
