import { useState } from "react";
import { usePRDashboardMembersQuery, usePRDashboardQuery } from "../hooks/usePRDashboardQuery";
import { usePRTrendsQuery } from "../hooks/usePRTrendsQuery";
import { useOrgStore } from "@/shared/store/orgStore";
import { KpiCard } from "./KpiCard";
import { MemberFilter } from "./MemberFilter";
import { PRThroughputChart } from "./PRThroughputChart";
import { ReviewLatencyChart } from "./ReviewLatencyChart";
import { formatHours, formatPercent } from "@/shared/charts/format";
import type { DashboardWindow } from "../lib/period";

interface Props {
  /** The dashboard's shared period (see `DashboardPage`/`PeriodSelector`).
   * Undefined while it's still resolving — the query stays disabled until
   * then rather than falling back to some other window. */
  window: DashboardWindow | undefined;
}

export function PRDashboardTab({ window }: Props) {
  const activeOrgId = useOrgStore((s) => s.activeOrgId);
  const [memberUserId, setMemberUserId] = useState<string>("");

  const { data, isLoading, isError } = usePRDashboardQuery(
    activeOrgId,
    memberUserId || undefined,
    window
  );
  const { data: members } = usePRDashboardMembersQuery(activeOrgId);
  const { data: trends, isLoading: trendsLoading } = usePRTrendsQuery(
    activeOrgId,
    memberUserId || undefined
  );

  if (isLoading || !window) {
    return <div className="p-4 text-muted-foreground">Ładowanie metryk PR...</div>;
  }

  if (isError || !data) {
    return (
      <div className="p-4 text-muted-foreground">
        Brak danych. Uruchom sync GitHub aby zobaczyć metryki PR.
      </div>
    );
  }

  // "Lower is better" for wait time — a delta computed the normal way
  // (positive = up) would need inverting to read as green/red correctly;
  // KpiCard's `invertDelta` handles that, this only computes the magnitude.
  const ttfrDeltaPct =
    data.time_to_first_review !== null &&
    data.time_to_first_review_prev !== null &&
    data.time_to_first_review_prev !== 0
      ? ((data.time_to_first_review - data.time_to_first_review_prev) /
          data.time_to_first_review_prev) *
        100
      : undefined;

  return (
    <div className="space-y-4">
      <MemberFilter
        value={memberUserId}
        onChange={setMemberUserId}
        items={members?.items.map((m) => ({
          user_id: m.user_id,
          display_name: m.display_name,
          disabled: m.github_login === null,
          hint: m.github_login === null ? "brak konta GitHub" : undefined,
        }))}
      />

      <div className="grid grid-cols-2 gap-4 md:grid-cols-3 lg:grid-cols-5">
        <KpiCard
          title="PR-y bez aktywności"
          value={data.stale_pr_count}
          hint={`Otwarte PR-y bez aktywności dłużej niż ${data.stale_threshold_days} dni (można zmienić w ustawieniach organizacji)`}
        />
        <KpiCard
          title="Oczekuje na review"
          value={data.awaiting_first_review}
          hint="Otwarte PR-y, które nie dostały jeszcze żadnego review"
        />
        <KpiCard
          title="Czas do 1. review (h)"
          value={data.time_to_first_review}
          delta={ttfrDeltaPct}
          invertDelta
          hint={`Średni czas do pierwszego review dla PR-ów otwartych w wybranym okresie (n=${data.cohort_size}); krócej = lepiej`}
          formatValue={formatHours}
        />
        <KpiCard
          title="Merged w okresie"
          value={data.weekly_throughput}
          hint="PR-y scalone w wybranym okresie"
        />
        <KpiCard
          title="% PR-ów z review"
          value={data.review_ratio !== null ? data.review_ratio * 100 : null}
          hint={`${data.reviewed_in_cohort} z ${data.cohort_size} PR-ów otwartych w okresie ma choć jedno review`}
          formatValue={formatPercent}
        />
      </div>

      <div className="grid gap-4 md:grid-cols-2">
        <PRThroughputChart data={trends} isLoading={trendsLoading} />
        <ReviewLatencyChart data={trends} isLoading={trendsLoading} />
      </div>
    </div>
  );
}
