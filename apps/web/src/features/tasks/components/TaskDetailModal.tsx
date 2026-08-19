import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";
import {
  Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter,
  Button, Input, Label,
  Select, SelectContent, SelectItem, SelectTrigger, SelectValue,
} from "@/shared/ui";
import type { Task } from "@/features/tasks/hooks/useTasksQuery";
import { useUpdateTask, useDeleteTask } from "@/features/tasks/hooks/useTaskMutations";
import { useOrgMembersQuery } from "@/features/organizations/hooks/useOrgMembers";
import { useOrgStore } from "@/shared/store/orgStore";
import { toDueDateIso, fromDueDateIso } from "@/features/tasks/lib/dueDate";
import { SprintSelect } from "@/features/tasks/components/SprintSelect";

const UNASSIGNED = "__unassigned__";

const STATUS_OPTIONS = [
  { value: "backlog", label: "Backlog" },
  { value: "todo", label: "To Do" },
  { value: "in_progress", label: "W toku" },
  { value: "review", label: "Review" },
  { value: "done", label: "Ukończone" },
  { value: "cancelled", label: "Anulowane" },
] as const;

const PRIORITY_OPTIONS = [
  { value: "low", label: "Niski" },
  { value: "medium", label: "Średni" },
  { value: "high", label: "Wysoki" },
  { value: "critical", label: "Krytyczny" },
] as const;

const UpdateSchema = z.object({
  title: z.string().min(1, "Tytuł jest wymagany"),
  description: z.string().optional(),
  status: z.enum(["backlog", "todo", "in_progress", "review", "done", "cancelled"]),
  priority: z.enum(["low", "medium", "high", "critical"]),
  assignee_id: z.string().nullable().optional(),
  due_date: z.string().optional(),
  // "" = backlog, else the sprint's start date (YYYY-MM-DD).
  sprint_start_date: z.string().optional(),
});
type UpdateData = z.infer<typeof UpdateSchema>;

interface Props {
  task: Task;
  open: boolean;
  onClose: () => void;
}

function formatDate(iso: string): string {
  return new Date(iso).toLocaleDateString("pl-PL", {
    year: "numeric",
    month: "long",
    day: "numeric",
  });
}

export function TaskDetailModal({ task, open, onClose }: Props) {
  const updateTask = useUpdateTask();
  const deleteTask = useDeleteTask();
  const { activeOrgId } = useOrgStore();
  const { data: members } = useOrgMembersQuery(activeOrgId);
  const creator = members?.find((m) => m.user_id === task.created_by);

  const { register, handleSubmit, setValue, watch, formState: { errors, dirtyFields } } = useForm<UpdateData>({
    resolver: zodResolver(UpdateSchema),
    defaultValues: {
      title: task.title,
      description: task.description ?? "",
      status: task.status,
      priority: task.priority,
      assignee_id: task.assignee_id ?? null,
      due_date: task.due_date ? fromDueDateIso(task.due_date) : "",
      sprint_start_date: task.sprint_start_date ?? "",
    },
  });

  const currentStatus = watch("status");
  const currentPriority = watch("priority");
  const currentAssignee = watch("assignee_id");
  const currentSprint = watch("sprint_start_date");

  function onSubmit(data: UpdateData) {
    const { sprint_start_date, ...rest } = data;
    updateTask.mutate(
      {
        taskId: task.id,
        data: {
          ...rest,
          due_date: data.due_date ? toDueDateIso(data.due_date) : null,
          // Only sent when the user actually touched this field — a task
          // whose stored sprint_start_date no longer matches the org's
          // current cadence (see OrgSprintsTab's warning) would otherwise
          // get re-sent unchanged on every save and 422 on the sprint
          // validation, even when editing something unrelated like the title.
          ...(dirtyFields.sprint_start_date
            ? { sprint_start_date: sprint_start_date || null }
            : {}),
        },
      },
      { onSuccess: onClose }
    );
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
            <Label htmlFor="modal-title">Tytuł</Label>
            <Input id="modal-title" {...register("title")} aria-invalid={!!errors.title} />
            {errors.title && <p className="text-sm text-destructive">{errors.title.message}</p>}
          </div>

          <div className="flex flex-col gap-1.5">
            <Label htmlFor="modal-description">Opis</Label>
            <textarea
              id="modal-description"
              className="flex min-h-[80px] w-full rounded-md border border-input bg-background px-3 py-2 text-sm ring-offset-background placeholder:text-muted-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 disabled:cursor-not-allowed disabled:opacity-50"
              {...register("description")}
            />
          </div>

          <div className="grid grid-cols-2 gap-4">
            <div className="flex flex-col gap-1.5">
              <Label>Status</Label>
              <Select value={currentStatus} onValueChange={(v) => setValue("status", v as UpdateData["status"])}>
                <SelectTrigger>
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  {STATUS_OPTIONS.map((opt) => (
                    <SelectItem key={opt.value} value={opt.value}>
                      {opt.label}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>

            <div className="flex flex-col gap-1.5">
              <Label>Priorytet</Label>
              <Select value={currentPriority} onValueChange={(v) => setValue("priority", v as UpdateData["priority"])}>
                <SelectTrigger>
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  {PRIORITY_OPTIONS.map((opt) => (
                    <SelectItem key={opt.value} value={opt.value}>
                      {opt.label}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
          </div>

          <div className="flex flex-col gap-1.5">
            <Label>Przypisano do</Label>
            <Select
              value={currentAssignee ?? UNASSIGNED}
              onValueChange={(v) =>
                setValue("assignee_id", v === UNASSIGNED ? null : v)
              }
            >
              <SelectTrigger aria-label="Przypisano do">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value={UNASSIGNED}>Nieprzypisane</SelectItem>
                {members?.map((m) => (
                  <SelectItem key={m.user_id} value={m.user_id}>
                    {m.display_name}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>

          <div className="flex flex-col gap-1.5">
            <Label htmlFor="modal-due-date">Termin</Label>
            <Input id="modal-due-date" type="date" {...register("due_date")} />
          </div>

          <div className="flex flex-col gap-1.5">
            <Label htmlFor="modal-sprint">Sprint</Label>
            <SprintSelect
              id="modal-sprint"
              value={currentSprint ?? ""}
              onChange={(v) =>
                setValue("sprint_start_date", v, { shouldDirty: true })
              }
            />
          </div>

          <p className="text-xs text-muted-foreground">
            Utworzono przez {creator?.display_name ?? "—"}, {formatDate(task.created_at)}
          </p>

          <DialogFooter className="flex-col gap-2 sm:flex-row sm:justify-between">
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
