import { useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { useProjectMetricsQuery, useProjectsQuery } from "@/features/projects/hooks/useProjectsQuery";
import { useArchiveProject } from "@/features/projects/hooks/useProjectMutations";
import { useTasksQuery } from "@/features/tasks/hooks/useTasksQuery";
import { TaskCard } from "@/features/tasks/components/TaskCard";
import { TaskDetailModal } from "@/features/tasks/components/TaskDetailModal";
import { CreateTaskModal } from "@/features/tasks/components/CreateTaskModal";
import type { Task } from "@/features/tasks/hooks/useTasksQuery";
import { Button } from "@/shared/ui";

export function ProjectDetailPage() {
  const { projectId } = useParams<{ projectId: string }>();
  const navigate = useNavigate();
  const [selectedTask, setSelectedTask] = useState<Task | null>(null);
  const [showCreate, setShowCreate] = useState(false);

  const { data: projectsData } = useProjectsQuery();
  const project = projectsData?.items.find((p) => p.id === projectId);

  const { data: metrics, isLoading: metricsLoading } = useProjectMetricsQuery(projectId ?? "");
  const { data: tasksData, isLoading: tasksLoading } = useTasksQuery({
    project_id: projectId ?? "",
  });

  const archiveProject = useArchiveProject();

  function handleArchive() {
    if (!projectId) return;
    if (confirm("Zarchiwizować projekt?")) {
      archiveProject.mutate(projectId, { onSuccess: () => void navigate("/projects") });
    }
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-semibold">{project?.name ?? "Projekt"}</h1>
        {project?.status === "active" && (
          <Button variant="destructive" onClick={handleArchive} disabled={archiveProject.isPending}>
            {archiveProject.isPending ? "Archiwizowanie..." : "Archiwizuj"}
          </Button>
        )}
      </div>

      <div>
        <h2 className="text-lg font-medium mb-4">Metryki projektu</h2>
        {metricsLoading && <p className="text-muted-foreground">Ładowanie metryk...</p>}
        {metrics && (
          <div className="grid grid-cols-2 gap-4 md:grid-cols-3">
            {metrics.total_tasks !== undefined && (
              <div className="rounded-lg border border-border bg-card p-4">
                <p className="text-sm text-muted-foreground">Łącznie zadań</p>
                <p className="text-2xl font-bold">{metrics.total_tasks}</p>
              </div>
            )}
            {metrics.completed_tasks !== undefined && (
              <div className="rounded-lg border border-border bg-card p-4">
                <p className="text-sm text-muted-foreground">Ukończonych</p>
                <p className="text-2xl font-bold">{metrics.completed_tasks}</p>
              </div>
            )}
            {metrics.total_hours !== undefined && (
              <div className="rounded-lg border border-border bg-card p-4">
                <p className="text-sm text-muted-foreground">Łącznie godzin</p>
                <p className="text-2xl font-bold">{Number(metrics.total_hours).toFixed(1)}</p>
              </div>
            )}
          </div>
        )}
      </div>

      <div>
        <div className="flex items-center justify-between mb-4">
          <h2 className="text-lg font-medium">Zadania</h2>
          <Button onClick={() => setShowCreate(true)}>Nowe zadanie</Button>
        </div>

        {tasksLoading && <p className="text-muted-foreground">Ładowanie zadań...</p>}

        {tasksData && (
          <div className="flex flex-col gap-3">
            {tasksData.items.length === 0 && (
              <p className="text-muted-foreground py-8 text-center">Brak zadań.</p>
            )}
            {tasksData.items.map((task) => (
              <TaskCard key={task.id} task={task} onClick={() => setSelectedTask(task)} />
            ))}
          </div>
        )}
      </div>

      {selectedTask && (
        <TaskDetailModal
          task={selectedTask}
          open={!!selectedTask}
          onClose={() => setSelectedTask(null)}
        />
      )}

      {projectId && (
        <CreateTaskModal open={showCreate} onClose={() => setShowCreate(false)} projectId={projectId} />
      )}
    </div>
  );
}
