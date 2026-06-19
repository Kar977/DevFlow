import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";
import {
  Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter,
  Button, Input, Label,
} from "@/shared/ui";
import type { Task } from "@/features/tasks/hooks/useTasksQuery";
import { useUpdateTask, useDeleteTask } from "@/features/tasks/hooks/useTaskMutations";

const UpdateSchema = z.object({
  title: z.string().min(1, "Tytuł jest wymagany"),
  description: z.string().optional(),
  status: z.enum(["backlog", "todo", "in_progress", "review", "done", "cancelled"]),
  priority: z.enum(["low", "medium", "high", "critical"]),
});
type UpdateData = z.infer<typeof UpdateSchema>;

interface Props {
  task: Task;
  open: boolean;
  onClose: () => void;
}

export function TaskDetailModal({ task, open, onClose }: Props) {
  const updateTask = useUpdateTask();
  const deleteTask = useDeleteTask();

  const { register, handleSubmit, formState: { errors } } = useForm<UpdateData>({
    resolver: zodResolver(UpdateSchema),
    defaultValues: {
      title: task.title,
      description: task.description ?? "",
      status: task.status,
      priority: task.priority,
    },
  });

  function onSubmit(data: UpdateData) {
    updateTask.mutate({ taskId: task.id, data }, { onSuccess: onClose });
  }

  function handleDelete() {
    if (confirm("Usuń zadanie?")) {
      deleteTask.mutate(task.id, { onSuccess: onClose });
    }
  }

  return (
    <Dialog open={open} onOpenChange={(v) => { if (!v) onClose(); }}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Szczegóły zadania</DialogTitle>
        </DialogHeader>
        <form onSubmit={handleSubmit(onSubmit)} className="flex flex-col gap-4">
          <div className="flex flex-col gap-1.5">
            <Label htmlFor="title">Tytuł</Label>
            <Input id="title" {...register("title")} aria-invalid={!!errors.title} />
            {errors.title && <p className="text-sm text-destructive">{errors.title.message}</p>}
          </div>
          <div className="flex flex-col gap-1.5">
            <Label htmlFor="description">Opis</Label>
            <Input id="description" {...register("description")} />
          </div>
          <DialogFooter className="flex justify-between">
            <Button type="button" variant="destructive" onClick={handleDelete} disabled={deleteTask.isPending}>
              Usuń
            </Button>
            <div className="flex gap-2">
              <Button type="button" variant="outline" onClick={onClose}>Anuluj</Button>
              <Button type="submit" disabled={updateTask.isPending}>
                {updateTask.isPending ? "Zapisywanie..." : "Zapisz"}
              </Button>
            </div>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}
