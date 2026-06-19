import type { Report } from "@/features/reports/hooks/useReportsQuery";

const CONFIG = {
  pending: { label: "Oczekuje", className: "bg-slate-100 text-slate-700" },
  generating: { label: "Generowanie...", className: "bg-yellow-100 text-yellow-700 animate-pulse" },
  ready: { label: "Gotowy", className: "bg-green-100 text-green-700" },
  failed: { label: "Błąd", className: "bg-red-100 text-red-700" },
} as const;

interface Props {
  status: Report["status"];
}

export function ReportStatusBadge({ status }: Props) {
  const { label, className } = CONFIG[status];
  return (
    <span className={`rounded-full px-2 py-0.5 text-xs font-medium ${className}`}>
      {label}
    </span>
  );
}
