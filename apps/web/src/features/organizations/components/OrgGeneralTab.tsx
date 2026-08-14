import { useEffect } from "react";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";
import { toast } from "sonner";
import { Button, Card, CardContent, CardHeader, CardTitle, Input, Label } from "@/shared/ui";
import { useOrgQuery } from "@/features/organizations/hooks/useOrgsQuery";
import { useUpdateOrganization } from "@/features/organizations/hooks/useOrgMutations";
import { getErrorMessage } from "@/shared/api/errorMessage";

const GeneralSchema = z.object({
  name: z.string().min(1, "Nazwa jest wymagana").max(255),
  description: z.string().optional(),
});
type GeneralData = z.infer<typeof GeneralSchema>;

interface Props {
  orgId: string;
  isAdmin: boolean;
}

export function OrgGeneralTab({ orgId, isAdmin }: Props) {
  const { data: org, isLoading } = useOrgQuery(orgId);
  const updateOrganization = useUpdateOrganization(orgId);

  const {
    register,
    handleSubmit,
    reset,
    formState: { errors },
  } = useForm<GeneralData>({
    resolver: zodResolver(GeneralSchema),
    values: org ? { name: org.name, description: org.description ?? "" } : undefined,
  });

  // Keep the form's baseline in sync once the detail query resolves, so a
  // slow first load doesn't leave stale defaultValues behind.
  useEffect(() => {
    if (org) reset({ name: org.name, description: org.description ?? "" });
  }, [org, reset]);

  function onSubmit(data: GeneralData) {
    updateOrganization.mutate(
      { name: data.name, description: data.description || null },
      {
        onSuccess: () => toast.success("Zapisano ustawienia organizacji."),
        onError: (err) =>
          toast.error(getErrorMessage(err, "Nie udało się zapisać zmian.")),
      }
    );
  }

  if (isLoading || !org) {
    return <p className="text-sm text-muted-foreground">Ładowanie...</p>;
  }

  return (
    <Card>
      <CardHeader>
        <CardTitle>Organizacja</CardTitle>
      </CardHeader>
      <CardContent>
        <form onSubmit={handleSubmit(onSubmit)} className="flex flex-col gap-4">
          <div className="flex flex-col gap-1.5">
            <Label htmlFor="org-name">Nazwa</Label>
            <Input
              id="org-name"
              {...register("name")}
              disabled={!isAdmin}
              aria-invalid={!!errors.name}
            />
            {errors.name && (
              <p className="text-sm text-destructive">{errors.name.message}</p>
            )}
          </div>

          <div className="flex flex-col gap-1.5">
            <Label htmlFor="org-description">Opis</Label>
            <textarea
              id="org-description"
              className="flex min-h-[80px] w-full rounded-md border border-input bg-background px-3 py-2 text-sm ring-offset-background focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 disabled:cursor-not-allowed disabled:opacity-50"
              disabled={!isAdmin}
              {...register("description")}
            />
          </div>

          <div className="flex flex-col gap-1">
            <span className="text-sm text-muted-foreground">Slug</span>
            <span className="text-sm font-mono">{org.slug}</span>
          </div>

          {!isAdmin && (
            <p className="text-xs text-muted-foreground">
              Tylko właściciele i administratorzy mogą edytować ustawienia organizacji.
            </p>
          )}

          {isAdmin && (
            <Button type="submit" disabled={updateOrganization.isPending} className="self-start">
              {updateOrganization.isPending ? "Zapisywanie..." : "Zapisz"}
            </Button>
          )}
        </form>
      </CardContent>
    </Card>
  );
}
