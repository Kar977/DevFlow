import { useState } from "react";
import {
  usePRDashboardMembersQuery,
  usePRDashboardQuery,
} from "../hooks/usePRDashboardQuery";
import { useOrgStore } from "@/shared/store/orgStore";
import { KpiCard } from "./KpiCard";

export function PRDashboardTab() {
  const activeOrgId = useOrgStore((s) => s.activeOrgId);
  const [memberUserId, setMemberUserId] = useState<string>("");

  const { data, isLoading, isError } = usePRDashboardQuery(
    activeOrgId,
    memberUserId || undefined
  );
  const { data: members } = usePRDashboardMembersQuery(activeOrgId);

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
    <div className="space-y-4">
      <div className="flex items-center gap-2">
        <label htmlFor="pr-member-filter" className="text-sm text-muted-foreground">
          Członek:
        </label>
        <select
          id="pr-member-filter"
          value={memberUserId}
          onChange={(e) => setMemberUserId(e.target.value)}
          className="rounded border border-border bg-background px-3 py-1.5 text-sm"
        >
          <option value="">Cały zespół</option>
          {members?.items.map((m) => (
            <option
              key={m.user_id}
              value={m.user_id}
              disabled={m.github_login === null}
            >
              {m.display_name}
              {m.github_login === null ? " (brak konta GitHub)" : ""}
            </option>
          ))}
        </select>
      </div>

      <div className="grid grid-cols-2 gap-4 md:grid-cols-3 lg:grid-cols-5">
        <KpiCard title="Stale PRs" value={data.stale_pr_count} />
        <KpiCard
          title="Czas do 1. review (h)"
          value={data.time_to_first_review ?? 0}
        />
        <KpiCard
          title="Velocity review (h)"
          value={data.review_velocity ?? 0}
        />
        <KpiCard title="Merged w tyg." value={data.weekly_throughput} />
        <KpiCard
          title="% z review"
          value={data.review_ratio !== null ? Math.round(data.review_ratio * 100) : 0}
        />
      </div>
    </div>
  );
}
