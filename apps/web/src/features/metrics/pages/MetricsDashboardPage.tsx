import { useState } from "react";
import { DateRangePicker } from "../components/DateRangePicker";
import { VelocityPanel } from "../components/VelocityPanel";
import { TimeTrackingPanel } from "../components/TimeTrackingPanel";
import { CompletionRatePanel } from "../components/CompletionRatePanel";
import { EstimationAccuracyPanel } from "../components/EstimationAccuracyPanel";
import { StreakPanel } from "../components/StreakPanel";
import { useMetricsQueries } from "../hooks/useMetricsQueries";

function defaultDateTo() {
  return new Date().toISOString().split("T")[0]!;
}

function defaultDateFrom() {
  const d = new Date();
  d.setDate(d.getDate() - 30);
  return d.toISOString().split("T")[0]!;
}

export function MetricsDashboardPage() {
  const [dateFrom, setDateFrom] = useState(defaultDateFrom);
  const [dateTo, setDateTo] = useState(defaultDateTo);

  const { velocity, timeTracking, completionRate, estimationAccuracy, streaks } = useMetricsQueries({
    date_from: dateFrom,
    date_to: dateTo,
  });

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between flex-wrap gap-4">
        <h1 className="text-2xl font-semibold">Metryki</h1>
        <DateRangePicker
          initialDateFrom={dateFrom}
          initialDateTo={dateTo}
          onApply={({ date_from, date_to }) => {
            setDateFrom(date_from);
            setDateTo(date_to);
          }}
        />
      </div>

      <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
        <VelocityPanel data={velocity.data} isLoading={velocity.isLoading} />
        <TimeTrackingPanel data={timeTracking.data} isLoading={timeTracking.isLoading} />
        <CompletionRatePanel data={completionRate.data} isLoading={completionRate.isLoading} />
        <EstimationAccuracyPanel data={estimationAccuracy.data} isLoading={estimationAccuracy.isLoading} />
        <StreakPanel data={streaks.data} isLoading={streaks.isLoading} />
      </div>
    </div>
  );
}
