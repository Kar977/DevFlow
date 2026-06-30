import { usePRDashboardQuery } from "../hooks/usePRDashboardQuery";
import { KpiCard } from "./KpiCard";

function fmt(value: number | null, suffix = ""): string {
  if (value === null) return "—";
  return `${value.toFixed(1)}${suffix}`;
}

export function PRDashboardTab() {
  const { data, isLoading, isError } = usePRDashboardQuery();

  if (isLoading) {
    return <div className="p-4 text-muted-foreground">Ładowanie metryk PR...</div>;
  }

  if (isError || !data) {
    return (
      <div className="p-4 text-muted-foreground">
        Brak danych. Uruchom sync GitHub aby zobaczyć metryki PR.
      </div>
    );
  }

  return (
    <div className="grid grid-cols-2 gap-4 md:grid-cols-3 lg:grid-cols-5">
      <KpiCard
        title="Stale PRs"
        value={data.stale_pr_count}
        delta={0}
      />
      <KpiCard
        title="Czas do 1. review (h)"
        value={data.time_to_first_review ?? 0}
        delta={0}
      />
      <KpiCard
        title="Velocity review (h)"
        value={data.review_velocity ?? 0}
        delta={0}
      />
      <KpiCard
        title="Merged w tyg."
        value={data.weekly_throughput}
        delta={0}
      />
      <KpiCard
        title="% z review"
        value={data.review_ratio !== null ? Math.round(data.review_ratio * 100) : 0}
        delta={0}
      />
    </div>
  );
}
