import { Info } from "lucide-react";
import { DEMO_BANNER_MESSAGE, IS_DEMO } from "@/shared/lib/demo";

/**
 * Persistent (non-dismissible) notice for the read-only public showcase
 * deployment — mounted once in AppShell, alongside StaleTimerBanner /
 * OverdueTasksBanner, so it's visible on every page a visitor lands on.
 * Renders nothing outside demo mode.
 */
export function DemoBanner() {
  if (!IS_DEMO) return null;

  return (
    <div
      role="status"
      className="mb-4 flex items-center gap-3 rounded-lg border border-blue-200 bg-blue-50 p-3 text-sm text-blue-900"
    >
      <Info className="h-4 w-4 shrink-0" />
      <p>{DEMO_BANNER_MESSAGE}</p>
    </div>
  );
}
