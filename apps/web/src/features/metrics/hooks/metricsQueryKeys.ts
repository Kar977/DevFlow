/**
 * Shared React Query key factory for the metrics feature.
 *
 * Exists so other features (tasks: `useTimerMutation`, `useTaskMutations`)
 * can invalidate "everything metrics-related" after a timer stop or a task
 * change, without importing the metrics feature's full public barrel
 * (`@/features/metrics`) — that barrel re-exports every chart panel, which
 * would drag the metrics feature's components into the tasks route chunk
 * for no reason. Import this leaf module directly instead.
 */
export const metricsQueryKeys = {
  all: ["metrics"] as const,
};
