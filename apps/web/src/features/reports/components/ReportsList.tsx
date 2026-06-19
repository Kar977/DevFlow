import { useDeleteReport } from "@/features/reports/hooks/useReportMutations";
import { ReportStatusBadge } from "./ReportStatusBadge";
import { Button } from "@/shared/ui";
import type { Report } from "@/features/reports/hooks/useReportsQuery";

const TYPE_LABELS: Record<Report["type"], string> = {
  weekly_summary: "Podsumowanie tygodniowe",
  project_status: "Status projektu",
  productivity_overview: "Przegląd produktywności",
};

interface Props {
  reports: Report[];
}

export function ReportsList({ reports }: Props) {
  const deleteReport = useDeleteReport();

  if (reports.length === 0) {
    return <p className="text-muted-foreground text-center py-8">Brak raportów.</p>;
  }

  return (
    <div className="flex flex-col gap-3">
      {reports.map((report) => (
        <div
          key={report.id}
          className="flex items-center justify-between rounded-lg border border-border bg-card p-4"
        >
          <div className="flex flex-col gap-1">
            <span className="font-medium">{TYPE_LABELS[report.type]}</span>
            <span className="text-sm text-muted-foreground">
              {new Date(report.created_at).toLocaleDateString("pl-PL")}
            </span>
          </div>
          <div className="flex items-center gap-3">
            <ReportStatusBadge status={report.status} />
            <Button
              variant="ghost"
              size="sm"
              onClick={() => deleteReport.mutate(report.id)}
              disabled={deleteReport.isPending}
              className="text-destructive hover:text-destructive"
            >
              Usuń
            </Button>
          </div>
        </div>
      ))}
    </div>
  );
}
