import { Info } from "lucide-react";
import { useQuery } from "@tanstack/react-query";
import { apiClient } from "@/shared/api/client";
import { DEMO_BANNER_MESSAGE, IS_DEMO } from "@/shared/lib/demo";

interface DemoStatusResponse {
  enabled: boolean;
  reset_interval_minutes: number;
  next_reset_at: string | null;
}

/** Refresh often enough that the countdown never looks stale to a visitor
 * staring at the banner, without hammering the endpoint. */
const STATUS_REFETCH_INTERVAL_MS = 60_000;

function useDemoStatus() {
  return useQuery({
    queryKey: ["demo", "status"],
    queryFn: async (): Promise<DemoStatusResponse> => {
      const r = await apiClient.get("/demo/status");
      return r.data as DemoStatusResponse;
    },
    enabled: IS_DEMO,
    refetchInterval: STATUS_REFETCH_INTERVAL_MS,
    staleTime: STATUS_REFETCH_INTERVAL_MS,
  });
}

/** "za ok. 12 min" / "za chwilę" — never negative, never a raw timestamp. */
function formatCountdown(nextResetAtIso: string): string {
  const minutes = Math.round((new Date(nextResetAtIso).getTime() - Date.now()) / 60_000);
  return minutes > 0 ? `za ok. ${minutes} min` : "za chwilę";
}

/**
 * Persistent (non-dismissible) notice for the public, editable showcase
 * deployment — mounted once in AppShell, alongside StaleTimerBanner /
 * OverdueTasksBanner, so it's visible on every page a visitor lands on.
 * Renders nothing outside demo mode.
 */
export function DemoBanner() {
  const { data } = useDemoStatus();

  if (!IS_DEMO) return null;

  const countdown = data?.next_reset_at ? formatCountdown(data.next_reset_at) : null;

  return (
    <div
      role="status"
      className="mb-4 flex items-center gap-3 rounded-lg border border-blue-200 bg-blue-50 p-3 text-sm text-blue-900"
    >
      <Info className="h-4 w-4 shrink-0" />
      <p>
        {DEMO_BANNER_MESSAGE}
        {countdown && <> Kolejny reset danych: {countdown}.</>}
      </p>
    </div>
  );
}
