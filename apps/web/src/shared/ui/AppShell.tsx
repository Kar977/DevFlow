import { Toaster } from "sonner";
import { useTimerSync } from "@/features/tasks/hooks/useTimerSync";
import { OverdueTasksBanner } from "@/features/tasks/components/OverdueTasksBanner";
import { StaleTimerBanner } from "@/features/tasks/components/StaleTimerBanner";
import { useEnsureTimezone } from "@/features/profile/hooks/useEnsureTimezone";
import { Sidebar } from "./Sidebar";
import { Topbar } from "./Topbar";

export function AppShell({ children }: { children: React.ReactNode }) {
  // Mounted once here so the active work session is loaded and kept in sync
  // regardless of which page the user is on — see useTimerSync for why.
  useTimerSync();
  // Same rationale: detect and persist the browser timezone once per
  // session, regardless of which page the user lands on first.
  useEnsureTimezone();

  return (
    <div className="flex h-screen overflow-hidden">
      <Toaster richColors position="top-right" />
      <Sidebar />
      <div className="flex flex-1 flex-col overflow-hidden">
        <Topbar />
        <main className="flex-1 overflow-y-auto p-6">
          <StaleTimerBanner />
          <OverdueTasksBanner />
          {children}
        </main>
      </div>
    </div>
  );
}
