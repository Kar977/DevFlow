import { useEffect } from "react";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";
import { toast } from "sonner";
import { Button, Card, CardContent, CardHeader, CardTitle, Input, Label } from "@/shared/ui";
import {
  useOrgSettingsQuery,
  useUpdateOrgSettings,
} from "@/features/organizations/hooks/useOrgSettings";
import { getErrorMessage } from "@/shared/api/errorMessage";

const MetricsSchema = z.object({
  stale_pr_threshold_days: z.coerce.number().int().min(1).max(90),
});
type MetricsData = z.infer<typeof MetricsSchema>;

interface Props {
  orgId: string;
  isAdmin: boolean;
}

export function OrgMetricsTab({ orgId, isAdmin }: Props) {
  const { data: settings, isLoading } = useOrgSettingsQuery(orgId);
  const updateSettings = useUpdateOrgSettings(orgId);

  const {
    register,
    handleSubmit,
    reset,
    formState: { errors },
  } = useForm<MetricsData>({
    resolver: zodResolver(MetricsSchema),
    values: settings
      ? {
          stale_pr_threshold_days: settings.stale_pr_threshold_days,
        }
      : undefined,
  });

  // Same rationale as OrgGeneralTab: keep the form baseline in sync once the
  // settings query resolves, so a slow first load doesn't leave stale
  // defaultValues behind.
  useEffect(() => {
    if (settings) {
      reset({
        stale_pr_threshold_days: settings.stale_pr_threshold_days,
      });
    }
  }, [settings, reset]);

  function onSubmit(data: MetricsData) {
    updateSettings.mutate(
      {
        stale_pr_threshold_days: data.stale_pr_threshold_days,
      },
      {
        onSuccess: () => toast.success("Zapisano ustawienia metryk."),
        onError: (err) =>
          toast.error(getErrorMessage(err, "Nie udało się zapisać zmian.")),
      }
    );
  }

  if (isLoading || !settings) {
    return <p className="text-sm text-muted-foreground">Ładowanie...</p>;
  }

  return (
    <Card>
      <CardHeader>
        <CardTitle>Metryki</CardTitle>
      </CardHeader>
      <CardContent>
        <form onSubmit={handleSubmit(onSubmit)} className="flex flex-col gap-4">
          <div className="flex flex-col gap-1.5">
            <Label htmlFor="stale-threshold">
              Próg „PR-y bez aktywności” (dni)
            </Label>
            <Input
              id="stale-threshold"
              type="number"
              min={1}
              max={90}
              {...register("stale_pr_threshold_days")}
              disabled={!isAdmin}
              aria-invalid={!!errors.stale_pr_threshold_days}
            />
            {errors.stale_pr_threshold_days && (
              <p className="text-sm text-destructive">
                {errors.stale_pr_threshold_days.message}
              </p>
            )}
          </div>

          {!isAdmin && (
            <p className="text-xs text-muted-foreground">
              Tylko właściciele i administratorzy mogą edytować ustawienia metryk.
            </p>
          )}

          {isAdmin && (
            <Button type="submit" disabled={updateSettings.isPending} className="self-start">
              {updateSettings.isPending ? "Zapisywanie..." : "Zapisz"}
            </Button>
          )}
        </form>
      </CardContent>
    </Card>
  );
}
