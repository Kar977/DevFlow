// Public surface of the metrics feature — consumed by the Dashboard's
// "Produktywność" tab so the four panels stay a single owned component
// instead of being copy-pasted (and drifting) across features.
export { VelocityPanel } from "./components/VelocityPanel";
export { TimeTrackingPanel } from "./components/TimeTrackingPanel";
export { CompletionRatePanel } from "./components/CompletionRatePanel";
export { EstimationAccuracyPanel } from "./components/EstimationAccuracyPanel";
export { StreakPanel } from "./components/StreakPanel";
export { MetricTrendsPanel } from "./components/MetricTrendsPanel";
export { useMetricsQueries } from "./hooks/useMetricsQueries";
export { useMetricTrendsQuery } from "./hooks/useMetricTrendsQuery";
