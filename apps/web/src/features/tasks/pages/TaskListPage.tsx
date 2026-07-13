import { useEffect, useState } from "react";
import { useOrgStore } from "@/shared/store/orgStore";
import { useTasksQuery } from "@/features/tasks/hooks/useTasksQuery";
import { useProjectsQuery } from "@/features/projects/hooks/useProjectsQuery";
import { TaskCard } from "@/features/tasks/components/TaskCard";
import { TaskFilters } from "@/features/tasks/components/TaskFilters";
import { TaskDetailModal } from "@/features/tasks/components/TaskDetailModal";
import { CreateTaskModal } from "@/features/tasks/components/CreateTaskModal";
import type { Task } from "@/features/tasks/hooks/useTasksQuery";
import {
  Button,
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/shared/ui";

export function TaskListPage() {
  const { activeOrgId } = useOrgStore();
  const [statusFilter, setStatusFilter] = useState("all");
  const [selectedTask, setSelectedTask] = useState<Task | null>(null);
  const [selectedProjectId, setSelectedProjectId] = useState("");
  const [showCreate, setShowCreate] = useState(false);

  const { data: projectsData } = useProjectsQuery();

  useEffect(() => {
    if (!selectedProjectId && projectsData?.items.length) {
      setSelectedProjectId(projectsData.items[0].id);
    }
  }, [projectsData, selectedProjectId]);

  const { data, isLoading } = useTasksQuery({
    project_id: selectedProjectId,
    status: statusFilter === "all" ? undefined : statusFilter,
  });

  if (!activeOrgId) {
    return (
      <div className="space-y-4">
        <h1 className="text-2xl font-semibold">Zadania</h1>
        <p className="text-muted-foreground">Wybierz organizację, aby zobaczyć zadania.</p>
      </div>
    );
  }

  if (projectsData && projectsData.items.length === 0) {
    return (
      <div className="space-y-4">
        <h1 className="text-2xl font-semibold">Zadania</h1>
        <p className="text-muted-foreground">
          Najpierw utwórz projekt, aby dodawać zadania.
        </p>
      </div>
    );
  }

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-semibold">Zadania</h1>
        <div className="flex items-center gap-2">
          {projectsData && (
            <Select value={selectedProjectId} onValueChange={setSelectedProjectId}>
              <SelectTrigger className="w-48">
                <SelectValue placeholder="Wybierz projekt" />
              </SelectTrigger>
              <SelectContent>
                {projectsData.items.map((project) => (
                  <SelectItem key={project.id} value={project.id}>
                    {project.name}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          )}
          <Button onClick={() => setShowCreate(true)} disabled={!selectedProjectId}>
            Nowe zadanie
          </Button>
        </div>
      </div>

      <TaskFilters status={statusFilter} onStatusChange={setStatusFilter} />

      {isLoading && <p className="text-muted-foreground">Ładowanie...</p>}

      {data && (
        <div className="flex flex-col gap-3">
          {data.items.length === 0 && (
            <p className="text-muted-foreground py-8 text-center">Brak zadań.</p>
          )}
          {data.items.map((task) => (
            <TaskCard key={task.id} task={task} onClick={() => setSelectedTask(task)} />
          ))}
        </div>
      )}

      {selectedTask && (
        <TaskDetailModal
          task={selectedTask}
          open={!!selectedTask}
          onClose={() => setSelectedTask(null)}
        />
      )}

      {selectedProjectId && (
        <CreateTaskModal
          open={showCreate}
          onClose={() => setShowCreate(false)}
          projectId={selectedProjectId}
        />
      )}
    </div>
  );
}
