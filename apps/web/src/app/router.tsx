import { lazy, Suspense } from "react";
import { createBrowserRouter, Navigate, Outlet } from "react-router-dom";
import { useAuthStore } from "@/shared/store/authStore";
import { LoginPage } from "@/features/auth/pages/LoginPage";
import { RegisterPage } from "@/features/auth/pages/RegisterPage";
import { DashboardPage } from "@/features/dashboard/pages/DashboardPage";
import { AppShell } from "@/shared/ui/AppShell";
import { GitHubCallbackPage } from "@/features/github/pages/GitHubCallbackPage";
import { GitHubSetupPage } from "@/features/github/pages/GitHubSetupPage";

const TaskListPage = lazy(() =>
  import("@/features/tasks/pages/TaskListPage").then((m) => ({ default: m.TaskListPage }))
);
const ProjectListPage = lazy(() =>
  import("@/features/projects/pages/ProjectListPage").then((m) => ({ default: m.ProjectListPage }))
);
const MetricsDashboardPage = lazy(() =>
  import("@/features/metrics/pages/MetricsDashboardPage").then((m) => ({ default: m.MetricsDashboardPage }))
);
const ReportListPage = lazy(() =>
  import("@/features/reports/pages/ReportListPage").then((m) => ({ default: m.ReportListPage }))
);
const GitHubIntegrationPage = lazy(() =>
  import("@/features/github/pages/GitHubIntegrationPage").then((m) => ({ default: m.GitHubIntegrationPage }))
);
const ProfilePage = lazy(() =>
  import("@/features/auth/pages/ProfilePage").then((m) => ({ default: m.ProfilePage }))
);
const ProjectDetailPage = lazy(() =>
  import("@/features/projects/pages/ProjectDetailPage").then((m) => ({ default: m.ProjectDetailPage }))
);
const PullRequestListPage = lazy(() =>
  import("@/features/pull-requests/pages/PullRequestListPage").then((m) => ({ default: m.PullRequestListPage }))
);
const PullRequestDetailPage = lazy(() =>
  import("@/features/pull-requests/pages/PullRequestDetailPage").then((m) => ({ default: m.PullRequestDetailPage }))
);
const RepositoryListPage = lazy(() =>
  import("@/features/repositories/pages/RepositoryListPage").then((m) => ({ default: m.RepositoryListPage }))
);
const OrganizationSettingsPage = lazy(() =>
  import("@/features/organizations/pages/OrganizationSettingsPage").then((m) => ({ default: m.OrganizationSettingsPage }))
);

export function ProtectedRoute() {
  const token = useAuthStore((s) => s.accessToken);
  if (!token) return <Navigate to="/login" replace />;
  return (
    <AppShell>
      <Suspense fallback={<div className="p-8 text-muted-foreground">Ładowanie...</div>}>
        <Outlet />
      </Suspense>
    </AppShell>
  );
}

export const router = createBrowserRouter([
  { path: "/login", element: <LoginPage /> },
  { path: "/register", element: <RegisterPage /> },
  { path: "/integrations/github/callback", element: <GitHubCallbackPage /> },
  { path: "/integrations/github/setup", element: <GitHubSetupPage /> },
  {
    path: "/",
    element: <ProtectedRoute />,
    children: [
      { index: true, element: <Navigate to="/dashboard" replace /> },
      { path: "dashboard", element: <DashboardPage /> },
      { path: "tasks", element: <TaskListPage /> },
      { path: "projects", element: <ProjectListPage /> },
      { path: "projects/:projectId", element: <ProjectDetailPage /> },
      { path: "pull-requests", element: <PullRequestListPage /> },
      { path: "pull-requests/:prId", element: <PullRequestDetailPage /> },
      { path: "repositories", element: <RepositoryListPage /> },
      { path: "metrics", element: <MetricsDashboardPage /> },
      { path: "reports", element: <ReportListPage /> },
      { path: "settings/github", element: <GitHubIntegrationPage /> },
      { path: "settings/profile", element: <ProfilePage /> },
      { path: "settings/organization", element: <OrganizationSettingsPage /> },
    ],
  },
  { path: "*", element: <Navigate to="/" replace /> },
]);
