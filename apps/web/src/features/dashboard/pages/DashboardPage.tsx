import { AreaChart, Area, XAxis, YAxis, Tooltip, ResponsiveContainer } from "recharts";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/shared/ui/tabs";
import { useDashboardData } from "../hooks/useDashboardData";
import { KpiCard } from "../components/KpiCard";
import { PRDashboardTab } from "../components/PRDashboardTab";

export function DashboardPage() {
  const { summary, velocity, isLoading } = useDashboardData();

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
                      value={summary.completed_tasks?.value ?? 0}
                      delta={summary.completed_tasks?.delta_pct ?? 0}
                    />
                    <KpiCard
                      title="Aktywne godziny"
                      value={summary.active_hours?.value ?? 0}
                      delta={summary.active_hours?.delta_pct ?? 0}
                    />
                  </>
                )}
              </div>

              {velocity?.weeks?.length > 0 && (
                <div className="rounded-lg border border-border bg-card p-6">
                  <h2 className="mb-4 text-sm font-medium text-muted-foreground">
                    Velocity (zadania/tydzień)
                  </h2>
                  <ResponsiveContainer width="100%" height={200}>
                    <AreaChart data={velocity.weeks}>
                      <XAxis dataKey="week" tick={{ fontSize: 12 }} />
                      <YAxis tick={{ fontSize: 12 }} />
                      <Tooltip />
                      <Area
                        type="monotone"
                        dataKey="tasks_closed"
                        stroke="#6366f1"
                        fill="#6366f120"
                      />
                    </AreaChart>
                  </ResponsiveContainer>
                </div>
              )}
            </div>
          )}
        </TabsContent>
      </Tabs>
    </div>
  );
}
