import { useParams } from "react-router-dom";
import { useProjectMetricsQuery } from "@/features/projects/hooks/useProjectsQuery";

export function ProjectDetailPage() {
  const { projectId } = useParams<{ projectId: string }>();

  const { data: metrics, isLoading: metricsLoading } = useProjectMetricsQuery(projectId ?? "");

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-semibold">Projekt</h1>

      <div>
        <h2 className="text-lg font-medium mb-4">Metryki projektu</h2>
        {metricsLoading && <p className="text-muted-foreground">Ładowanie metryk...</p>}
        {metrics && (
          <div className="grid grid-cols-2 gap-4 md:grid-cols-3">
            {metrics.total_tasks !== undefined && (
              <div className="rounded-lg border border-border bg-card p-4">
                <p className="text-sm text-muted-foreground">Łącznie zadań</p>
                <p className="text-2xl font-bold">{metrics.total_tasks}</p>
              </div>
            )}
            {metrics.completed_tasks !== undefined && (
              <div className="rounded-lg border border-border bg-card p-4">
                <p className="text-sm text-muted-foreground">Ukończonych</p>
                <p className="text-2xl font-bold">{metrics.completed_tasks}</p>
              </div>
            )}
            {metrics.total_hours !== undefined && (
              <div className="rounded-lg border border-border bg-card p-4">
                <p className="text-sm text-muted-foreground">Łącznie godzin</p>
                <p className="text-2xl font-bold">{Number(metrics.total_hours).toFixed(1)}</p>
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
}
