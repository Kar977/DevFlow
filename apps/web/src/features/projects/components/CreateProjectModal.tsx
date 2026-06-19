import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";
import {
  Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter,
  Button, Input, Label,
} from "@/shared/ui";
import { useOrgStore } from "@/shared/store/orgStore";
import { useCreateProject } from "@/features/projects/hooks/useProjectMutations";

const CreateProjectSchema = z.object({
  name: z.string().min(1, "Nazwa jest wymagana"),
  description: z.string().optional(),
  github_repo_url: z.string().url("Podaj prawidłowy URL").optional().or(z.literal("")),
});
type CreateProjectData = z.infer<typeof CreateProjectSchema>;

interface Props {
  open: boolean;
  onClose: () => void;
}

export function CreateProjectModal({ open, onClose }: Props) {
  const { activeOrgId } = useOrgStore();
  const createProject = useCreateProject();

  const { register, handleSubmit, reset, formState: { errors } } = useForm<CreateProjectData>({
    resolver: zodResolver(CreateProjectSchema),
  });

  function onSubmit(data: CreateProjectData) {
    if (!activeOrgId) return;
    createProject.mutate(
      {
        name: data.name,
        description: data.description ?? undefined,
        github_repo_url: data.github_repo_url || undefined,
        org_id: activeOrgId,
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
    <Dialog open={open} onOpenChange={(v) => { if (!v) { reset(); onClose(); } }}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Nowy projekt</DialogTitle>
        </DialogHeader>
        <form onSubmit={handleSubmit(onSubmit)} className="flex flex-col gap-4">
          <div className="flex flex-col gap-1.5">
            <Label htmlFor="proj-name">Nazwa *</Label>
            <Input id="proj-name" {...register("name")} aria-invalid={!!errors.name} />
            {errors.name && <p className="text-sm text-destructive">{errors.name.message}</p>}
          </div>
          <div className="flex flex-col gap-1.5">
            <Label htmlFor="proj-desc">Opis</Label>
            <textarea
              id="proj-desc"
              className="flex min-h-[80px] w-full rounded-md border border-input bg-background px-3 py-2 text-sm ring-offset-background focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2"
              {...register("description")}
            />
          </div>
          <div className="flex flex-col gap-1.5">
            <Label htmlFor="proj-url">GitHub URL (opcjonalnie)</Label>
            <Input id="proj-url" type="url" {...register("github_repo_url")} aria-invalid={!!errors.github_repo_url} />
            {errors.github_repo_url && (
              <p className="text-sm text-destructive">{errors.github_repo_url.message}</p>
            )}
          </div>
          <DialogFooter>
            <Button type="button" variant="outline" onClick={() => { reset(); onClose(); }}>Anuluj</Button>
            <Button type="submit" disabled={createProject.isPending}>
              {createProject.isPending ? "Tworzenie..." : "Utwórz"}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}
