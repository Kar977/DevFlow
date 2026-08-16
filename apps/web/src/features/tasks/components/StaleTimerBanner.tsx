import { useState } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { AlertTriangle, X } from "lucide-react";
import { toast } from "sonner";
import { apiClient } from "@/shared/api/client";
import { getErrorMessage } from "@/shared/api/errorMessage";
import { useTimerStore } from "@/shared/store/timerStore";
import { Button } from "@/shared/ui";
import { activeSessionKey } from "@/features/tasks/hooks/useActiveSessionQuery";
import { taskQueryKeys } from "@/features/tasks/hooks/useTasksQuery";
import { useLongRunningTimer } from "@/features/tasks/hooks/useLongRunningTimer";
import { formatTrackedTime } from "@/features/tasks/lib/trackedTime";

const DISMISSED_KEY = "devflow-stale-timer-dismissed-hours";

function readDismissedHours(): number {
  const raw = sessionStorage.getItem(DISMISSED_KEY);
  const parsed = raw ? Number(raw) : 0;
  return Number.isFinite(parsed) ? parsed : 0;
}

/**
 * Warning shown once the running timer has been active past the configured
 * threshold — almost certainly forgotten (closed laptop, switched tasks
 * without stopping it), which otherwise silently inflates time-tracking and
 * estimation-accuracy metrics. Mounted once in AppShell, above
 * OverdueTasksBanner (see that component for the dismissal-banner precedent
 * this one follows).
 *
 * Dismissal is keyed by whole hours of elapsed time rather than a fixed
 * value: closing the banner hides it until the timer has run for another
 * full hour, so a genuinely forgotten timer keeps re-surfacing instead of
 * going silent for the rest of the day.
 */
export function StaleTimerBanner() {
  const timer = useLongRunningTimer();
  const [dismissedHours, setDismissedHours] = useState(readDismissedHours);
  const qc = useQueryClient();
  const stopSession = useTimerStore((s) => s.stopSession);

  const stop = useMutation({
    mutationFn: (taskId: string) => apiClient.post(`/tasks/${taskId}/stop`),
    onSuccess: () => {
      stopSession();
      void qc.invalidateQueries({ queryKey: taskQueryKeys.all });
      void qc.invalidateQueries({ queryKey: activeSessionKey });
    },
    onError: (error) => {
      toast.error(getErrorMessage(error, "Nie udało się zatrzymać timera."));
      void qc.invalidateQueries({ queryKey: activeSessionKey });
    },
  });

  if (!timer) return null;
  const currentHour = Math.floor(timer.elapsedSeconds / 3600);
  if (currentHour <= dismissedHours) return null;

  return (
    <div
      role="alert"
      className="mb-4 flex items-start gap-3 rounded-lg border border-amber-200 bg-amber-50 p-4 text-amber-900"
    >
      <AlertTriangle className="h-5 w-5 shrink-0" />
      <div className="flex-1 space-y-1">
        <p className="text-sm font-medium">
          Timer na „{timer.taskTitle}" działa już {formatTrackedTime(timer.elapsedSeconds)}.
        </p>
        <p className="text-sm">
          Jeśli zapomniałeś go zatrzymać, zawyży to śledzony czas pracy.
        </p>
        <Button
          size="sm"
          variant="outline"
          onClick={() => stop.mutate(timer.taskId)}
          disabled={stop.isPending}
        >
          Zatrzymaj timer
        </Button>
      </div>
      <button
        type="button"
        aria-label="Zamknij"
        className="shrink-0 text-amber-900/70 hover:text-amber-900"
        onClick={() => {
          sessionStorage.setItem(DISMISSED_KEY, String(currentHour));
          setDismissedHours(currentHour);
        }}
      >
        <X className="h-4 w-4" />
      </button>
    </div>
  );
}
