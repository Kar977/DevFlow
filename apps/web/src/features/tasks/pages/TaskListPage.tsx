import { useState } from "react";
import { useOrgStore } from "@/shared/store/orgStore";
import { useTasksQuery } from "@/features/tasks/hooks/useTasksQuery";
import { TaskCard } from "@/features/tasks/components/TaskCard";
import { TaskFilters } from "@/features/tasks/components/TaskFilters";
import { TaskDetailModal } from "@/features/tasks/components/TaskDetailModal";
import type { Task } from "@/features/tasks/hooks/useTasksQuery";

export function TaskListPage() {
  const { activeOrgId } = useOrgStore();
  const [statusFilter, setStatusFilter] = useState("all");
  const [selectedTask, setSelectedTask] = useState<Task | null>(null);

  // We query tasks for the whole org — in practice the user would select a project
  // For now use a placeholder project_id based on org
  const { data, isLoading } = useTasksQuery({
    project_id: activeOrgId ?? "none",
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

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-semibold">Zadania</h1>
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
    </div>
  );
}
