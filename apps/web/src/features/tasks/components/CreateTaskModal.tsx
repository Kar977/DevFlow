import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogFooter,
  Button,
  Input,
  Label,
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/shared/ui";
import { useCreateTask } from "@/features/tasks/hooks/useTaskMutations";

const PRIORITY_OPTIONS = [
  { value: "low", label: "Niski" },
  { value: "medium", label: "Średni" },
  { value: "high", label: "Wysoki" },
  { value: "critical", label: "Krytyczny" },
] as const;

const CreateTaskSchema = z.object({
  title: z.string().min(1, "Tytuł jest wymagany"),
  description: z.string().optional(),
  priority: z.enum(["low", "medium", "high", "critical"]),
  estimate_minutes: z
    .number({ invalid_type_error: "Podaj liczbę minut" })
    .int()
    .positive("Podaj dodatnią liczbę minut")
    .optional(),
});
type CreateTaskData = z.infer<typeof CreateTaskSchema>;

interface Props {
  open: boolean;
  onClose: () => void;
  projectId: string;
}

export function CreateTaskModal({ open, onClose, projectId }: Props) {
  const createTask = useCreateTask(projectId);

  const {
    register,
    handleSubmit,
    reset,
    setValue,
    watch,
    formState: { errors },
  } = useForm<CreateTaskData>({
    resolver: zodResolver(CreateTaskSchema),
    defaultValues: { priority: "medium" },
  });

  const currentPriority = watch("priority");

  function onSubmit(data: CreateTaskData) {
    createTask.mutate(
      {
        title: data.title,
        description: data.description || undefined,
        priority: data.priority,
        estimate_minutes: data.estimate_minutes,
      },
      {
        onSuccess: () => {
          reset();
          onClose();
        },
      }
    );
  }

  return (
    <Dialog
      open={open}
      onOpenChange={(v) => {
        if (!v) {
          reset();
          onClose();
        }
      }}
    >
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Nowe zadanie</DialogTitle>
        </DialogHeader>
        <form onSubmit={handleSubmit(onSubmit)} className="flex flex-col gap-4">
          <div className="flex flex-col gap-1.5">
            <Label htmlFor="task-title">Tytuł *</Label>
            <Input id="task-title" {...register("title")} aria-invalid={!!errors.title} />
            {errors.title && <p className="text-sm text-destructive">{errors.title.message}</p>}
          </div>

          <div className="flex flex-col gap-1.5">
            <Label htmlFor="task-description">Opis</Label>
            <textarea
              id="task-description"
              className="flex min-h-[80px] w-full rounded-md border border-input bg-background px-3 py-2 text-sm ring-offset-background focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2"
              {...register("description")}
            />
          </div>

          <div className="grid grid-cols-2 gap-4">
            <div className="flex flex-col gap-1.5">
              <Label>Priorytet</Label>
              <Select
                value={currentPriority}
                onValueChange={(v) => setValue("priority", v as CreateTaskData["priority"])}
              >
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

            <div className="flex flex-col gap-1.5">
              <Label htmlFor="task-estimate">Szacowany czas (min)</Label>
              <Input
                id="task-estimate"
                type="number"
                min={1}
                {...register("estimate_minutes", {
                  setValueAs: (v) => (v === "" ? undefined : Number(v)),
                })}
                aria-invalid={!!errors.estimate_minutes}
              />
              {errors.estimate_minutes && (
                <p className="text-sm text-destructive">{errors.estimate_minutes.message}</p>
              )}
            </div>
          </div>

          <DialogFooter>
            <Button
              type="button"
              variant="outline"
              onClick={() => {
                reset();
                onClose();
              }}
            >
              Anuluj
            </Button>
            <Button type="submit" disabled={createTask.isPending}>
              {createTask.isPending ? "Tworzenie..." : "Utwórz"}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}
