import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/shared/ui/tabs";
import { useDashboardData } from "../hooks/useDashboardData";
import { KpiCard } from "../components/KpiCard";
import { PRDashboardTab } from "../components/PRDashboardTab";
import {
  VelocityPanel,
  TimeTrackingPanel,
  CompletionRatePanel,
  EstimationAccuracyPanel,
  useMetricsQueries,
} from "@/features/metrics";
import { daysAgoLocal, todayLocal } from "@/shared/lib/localDate";

export function DashboardPage() {
  const { summary, velocity, isLoading } = useDashboardData();
  // Same 30-day default window `useDashboardData` uses for velocity/summary
  // — react-query dedupes the shared `["metrics", "velocity", params]`
  // query automatically as long as the params match, so no extra request.
  const { timeTracking, completionRate, estimationAccuracy } = useMetricsQueries({
    date_from: daysAgoLocal(30),
    date_to: todayLocal(),
  });

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-semibold">Dashboard</h1>

      <Tabs defaultValue="flow">
        <TabsList>
          <TabsTrigger value="flow">Flow</TabsTrigger>
          <TabsTrigger value="productivity">Produktywność</TabsTrigger>
        </TabsList>

        <TabsContent value="flow">
          <PRDashboardTab />
        </TabsContent>

        <TabsContent value="productivity">
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
