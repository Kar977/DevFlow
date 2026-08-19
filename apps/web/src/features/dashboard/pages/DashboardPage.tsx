import { useState } from "react";
import { useSearchParams } from "react-router-dom";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/shared/ui/tabs";
import { useDashboardData } from "../hooks/useDashboardData";
import { KpiCard } from "../components/KpiCard";
import { MemberFilter } from "../components/MemberFilter";
import { PRDashboardTab } from "../components/PRDashboardTab";
import { PeriodSelector } from "../components/PeriodSelector";
import {
  VelocityPanel,
  TimeTrackingPanel,
  CompletionRatePanel,
  EstimationAccuracyPanel,
  useMetricsQueries,
} from "@/features/metrics";
import { useOrgMembersQuery } from "@/features/organizations/hooks/useOrgMembers";
import { useOrgSprintsQuery } from "@/features/organizations/hooks/useOrgSprints";
import { useOrgStore } from "@/shared/store/orgStore";
import { daysAgoLocal, todayLocal } from "@/shared/lib/localDate";
import { windowFromSprints, type DashboardWindow, type PeriodMode } from "../lib/period";

const VALID_MODES: readonly PeriodMode[] = ["current", "previous", "custom"];

function isPeriodMode(value: string | null): value is PeriodMode {
  return VALID_MODES.includes(value as PeriodMode);
}

export function DashboardPage() {
  const activeOrgId = useOrgStore((s) => s.activeOrgId);
  const [memberUserId, setMemberUserId] = useState<string>("");
  const { data: members } = useOrgMembersQuery(activeOrgId);

  // The period is shared by both tabs and kept in the URL so it survives a
  // reload and can be sent as a link — previously "Flow" defaulted to the
  // current sprint while "Produktywność" was hardcoded to 30 days, so the
  // two tabs silently disagreed about what "the period" even meant.
  const [searchParams, setSearchParams] = useSearchParams();
  const [mode, setMode] = useState<PeriodMode>(() => {
    const fromUrl = searchParams.get("period");
    return isPeriodMode(fromUrl) ? fromUrl : "current";
  });
  const [customRange, setCustomRange] = useState<DashboardWindow>(() => ({
    date_from: searchParams.get("from") ?? daysAgoLocal(30),
    date_to: searchParams.get("to") ?? todayLocal(),
  }));

  const { data: sprints } = useOrgSprintsQuery(activeOrgId, { back: 1, forward: 0 });
  // `number` is null for every sprint when the org has no cadence
  // configured (see core.services.period.sprint_series) — used to disable
  // the sprint-based options rather than let them silently resolve to
  // nothing.
  const sprintsAvailable = sprints ? sprints.some((s) => s.number !== null) : true;

  const window: DashboardWindow | undefined =
    mode === "custom" ? customRange : windowFromSprints(sprints, mode);

  function updateMode(next: PeriodMode) {
    setMode(next);
    const params = new URLSearchParams(searchParams);
    params.set("period", next);
    if (next !== "custom") {
      params.delete("from");
      params.delete("to");
    }
    setSearchParams(params, { replace: true });
  }

  function updateCustomRange(range: DashboardWindow) {
    setCustomRange(range);
    const params = new URLSearchParams(searchParams);
    params.set("period", "custom");
    params.set("from", range.date_from);
    params.set("to", range.date_to);
    setSearchParams(params, { replace: true });
  }

  const orgArg = activeOrgId ?? undefined;
  const memberArg = memberUserId || undefined;

  const { summary, velocity, isLoading } = useDashboardData(
    orgArg,
    memberArg,
    window,
    !!window
  );
  const { timeTracking, completionRate, estimationAccuracy } = useMetricsQueries({
    date_from: window?.date_from ?? "",
    date_to: window?.date_to ?? "",
    organizationId: orgArg,
    memberUserId: memberArg,
    enabled: !!window,
  });

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-semibold">Dashboard</h1>

      <PeriodSelector
        mode={mode}
        onModeChange={updateMode}
        customRange={customRange}
        onCustomRangeChange={updateCustomRange}
        effectiveWindow={window}
        sprintsAvailable={sprintsAvailable}
      />

      <Tabs defaultValue="flow">
        <TabsList>
          <TabsTrigger value="flow">Flow</TabsTrigger>
          <TabsTrigger value="productivity">Produktywność</TabsTrigger>
        </TabsList>

        <TabsContent value="flow">
          <PRDashboardTab window={window} />
        </TabsContent>

        <TabsContent value="productivity">
          <div className="mb-4 flex flex-wrap items-center justify-between gap-2">
            <MemberFilter
              value={memberUserId}
              onChange={setMemberUserId}
              items={members?.map((m) => ({
                user_id: m.user_id,
                display_name: m.display_name,
              }))}
              id="productivity-member-filter"
            />
          </div>

          {isLoading ? (
            <div className="p-4 text-muted-foreground">Ładowanie...</div>
          ) : (
            <div className="space-y-6">
              <div className="grid grid-cols-2 gap-4 md:grid-cols-4">
                {summary && (
                  <>
                    <KpiCard
                      title="Ukończone zadania"
                      value={summary.tasks_completed?.value ?? 0}
                      delta={summary.tasks_completed?.delta_pct ?? 0}
                    />
                    <KpiCard
                      title="Aktywne godziny"
                      value={summary.active_hours?.value ?? 0}
                      delta={summary.active_hours?.delta_pct ?? 0}
                    />
                  </>
                )}
              </div>

              <div className="grid gap-4 md:grid-cols-2">
                <VelocityPanel data={velocity} />
                <TimeTrackingPanel
                  data={timeTracking.data}
                  isLoading={timeTracking.isLoading}
                />
                <CompletionRatePanel
                  data={completionRate.data}
                  isLoading={completionRate.isLoading}
                />
                <EstimationAccuracyPanel
                  data={estimationAccuracy.data}
                  isLoading={estimationAccuracy.isLoading}
                />
              </div>
            </div>
          )}
        </TabsContent>
      </Tabs>
    </div>
  );
}
