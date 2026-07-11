import { NavLink } from "react-router-dom";
import {
  LayoutDashboard,
  CheckSquare,
  FolderOpen,
  BarChart2,
  FileText,
  Github,
  User,
  GitPullRequest,
  GitBranch,
  Building2,
} from "lucide-react";
import { cn } from "@/shared/lib/utils";
import { useTimerStore } from "@/shared/store/timerStore";

const navItems = [
  { to: "/dashboard", icon: LayoutDashboard, label: "Dashboard" },
  { to: "/pull-requests", icon: GitPullRequest, label: "Pull Requests" },
  { to: "/repositories", icon: GitBranch, label: "Repozytoria" },
  { to: "/tasks", icon: CheckSquare, label: "Zadania" },
  { to: "/projects", icon: FolderOpen, label: "Projekty" },
  { to: "/metrics", icon: BarChart2, label: "Metryki" },
  { to: "/reports", icon: FileText, label: "Raporty" },
];

const settingsItems = [
  { to: "/settings/github", icon: Github, label: "GitHub" },
  { to: "/settings/profile", icon: User, label: "Profil" },
  { to: "/settings/organization", icon: Building2, label: "Organizacja" },
];

function NavItem({ to, icon: Icon, label }: { to: string; icon: React.ElementType; label: string }) {
  return (
    <NavLink
      to={to}
      className={({ isActive }) =>
        cn(
          "flex items-center gap-3 rounded-lg px-3 py-2 text-sm font-medium transition-colors",
          isActive
            ? "bg-primary text-primary-foreground"
            : "text-muted-foreground hover:bg-accent hover:text-accent-foreground"
        )
      }
    >
      <Icon className="h-4 w-4 shrink-0" />
      {label}
    </NavLink>
  );
}

function TimerIndicator() {
  const { activeSession, elapsedSeconds } = useTimerStore();
  if (!activeSession) return null;

  const minutes = Math.floor(elapsedSeconds / 60);
  const seconds = elapsedSeconds % 60;
  const formatted = `${String(minutes).padStart(2, "0")}:${String(seconds).padStart(2, "0")}`;

  return (
    <div className="mx-3 mt-auto rounded-lg border border-border bg-muted p-3 text-sm">
      <p className="font-medium text-foreground truncate">{activeSession.taskTitle}</p>
      <p className="text-muted-foreground tabular-nums">{formatted}</p>
    </div>
  );
}

export function Sidebar() {
  return (
    <aside className="flex h-screen w-56 flex-col border-r border-border bg-card px-3 py-4">
      <div className="mb-6 px-3">
        <span className="text-lg font-bold">DevFlow</span>
      </div>
      <nav className="flex flex-col gap-1">
        {navItems.map((item) => (
          <NavItem key={item.to} {...item} />
        ))}
      </nav>
      <div className="my-4">
        <div className="border-t border-border" />
      </div>
      <nav className="flex flex-col gap-1">
        {settingsItems.map((item) => (
          <NavItem key={item.to} {...item} />
        ))}
      </nav>
      <TimerIndicator />
    </aside>
  );
}
