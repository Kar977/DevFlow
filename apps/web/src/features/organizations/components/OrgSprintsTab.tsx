import { useEffect } from "react";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";
import { toast } from "sonner";
import { AlertTriangle } from "lucide-react";
import {
  Badge,
  Button,
  Card,
  CardContent,
  CardHeader,
  CardTitle,
  Input,
  Label,
} from "@/shared/ui";
import {
  useOrgSettingsQuery,
  useUpdateOrgSettings,
} from "@/features/organizations/hooks/useOrgSettings";
import { useOrgSprintsQuery } from "@/features/organizations/hooks/useOrgSprints";
import { formatSprintDate } from "@/features/organizations/lib/sprintFormat";
import { getErrorMessage } from "@/shared/api/errorMessage";

const SprintCadenceSchema = z.object({
  sprint_length_days: z.coerce.number().int().min(1).max(60),
  sprint_anchor_date: z.string().optional(),
});
type SprintCadenceData = z.infer<typeof SprintCadenceSchema>;

interface Props {
  orgId: string;
  isAdmin: boolean;
}

export function OrgSprintsTab({ orgId, isAdmin }: Props) {
  const { data: settings, isLoading } = useOrgSettingsQuery(orgId);
  const updateSettings = useUpdateOrgSettings(orgId);
  const { data: sprints, isLoading: sprintsLoading } = useOrgSprintsQuery(orgId, {
    back: 2,
    forward: 3,
  });

  const {
    register,
    handleSubmit,
    reset,
    formState: { errors },
  } = useForm<SprintCadenceData>({
    resolver: zodResolver(SprintCadenceSchema),
    values: settings
      ? {
          sprint_length_days: settings.sprint_length_days,
          sprint_anchor_date: settings.sprint_anchor_date ?? "",
        }
      : undefined,
  });

  // Same rationale as OrgMetricsTab: keep the form baseline in sync once the
  // settings query resolves, so a slow first load doesn't leave stale
  // defaultValues behind.
  useEffect(() => {
    if (settings) {
      reset({
        sprint_length_days: settings.sprint_length_days,
        sprint_anchor_date: settings.sprint_anchor_date ?? "",
      });
    }
  }, [settings, reset]);

  function onSubmit(data: SprintCadenceData) {
    updateSettings.mutate(
      {
        sprint_length_days: data.sprint_length_days,
        sprint_anchor_date: data.sprint_anchor_date || null,
      },
      {
        onSuccess: () => toast.success("Zapisano kadencję sprintu."),
        onError: (err) =>
          toast.error(getErrorMessage(err, "Nie udało się zapisać zmian.")),
      }
    );
  }

  if (isLoading || !settings) {
    return <p className="text-sm text-muted-foreground">Ładowanie...</p>;
  }

  const cadenceConfigured = settings.sprint_anchor_date !== null;

  return (
    <div className="flex flex-col gap-4">
      <Card>
        <CardHeader>
          <CardTitle>Sprinty</CardTitle>
        </CardHeader>
        <CardContent>
          <form onSubmit={handleSubmit(onSubmit)} className="flex flex-col gap-4">
            <div className="flex flex-col gap-1.5">
              <Label htmlFor="sprint-length">Długość sprintu (dni)</Label>
              <Input
                id="sprint-length"
                type="number"
                min={1}
                max={60}
                {...register("sprint_length_days")}
                disabled={!isAdmin}
                aria-invalid={!!errors.sprint_length_days}
              />
              {errors.sprint_length_days && (
                <p className="text-sm text-destructive">
                  {errors.sprint_length_days.message}
                </p>
              )}
            </div>

            <div className="flex flex-col gap-1.5">
              <Label htmlFor="sprint-anchor">Data startu sprintu referencyjnego</Label>
              <Input
                id="sprint-anchor"
                type="date"
                {...register("sprint_anchor_date")}
                disabled={!isAdmin}
              />
              <p className="text-xs text-muted-foreground">
                Dowolna data startu jednego ze sprintów — pozostałe wyliczają się
                z tej cadencji.
              </p>
            </div>

            {!cadenceConfigured && (
              <div
                role="alert"
                className="flex items-start gap-3 rounded-lg border border-amber-200 bg-amber-50 p-3 text-amber-900"
              >
                <AlertTriangle className="h-4 w-4 shrink-0 translate-y-0.5" />
                <p className="text-sm">
                  Kadencja nie jest skonfigurowana: okna metryk liczone są jako
                  tygodnie kalendarzowe (poniedziałek–niedziela), długość sprintu
                  powyżej jest wtedy ignorowana, a zadań nie można przypisać do
                  konkretnego sprintu. Ustaw datę startu, aby to włączyć.
                </p>
              </div>
            )}

            <p className="text-xs text-muted-foreground">
              Zmiana kadencji nie przenosi zadań już przypisanych do sprintów —
              zadania spoza nowej kadencji zostaną oznaczone jako „poza kadencją”.
            </p>

            {!isAdmin && (
              <p className="text-xs text-muted-foreground">
                Tylko właściciele i administratorzy mogą edytować kadencję sprintu.
              </p>
            )}

            {isAdmin && (
              <Button
                type="submit"
                disabled={updateSettings.isPending}
                className="self-start"
              >
                {updateSettings.isPending ? "Zapisywanie..." : "Zapisz"}
              </Button>
            )}
          </form>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Podgląd sprintów</CardTitle>
        </CardHeader>
        <CardContent>
          {sprintsLoading ? (
            <p className="text-sm text-muted-foreground">Ładowanie...</p>
          ) : !sprints || sprints.length === 0 ? (
            <p className="text-sm text-muted-foreground">
              Brak podglądu — skonfiguruj datę startu powyżej.
            </p>
          ) : (
            <ul className="flex flex-col gap-1.5">
              {sprints.map((sprint) => (
                <li
                  key={sprint.start_date}
                  className="flex items-center gap-2 text-sm"
                >
                  <span>
                    {sprint.number !== null
                      ? `Sprint ${sprint.number} · `
                      : ""}
                    {formatSprintDate(sprint.start_date)} –{" "}
                    {formatSprintDate(sprint.end_date)}
                  </span>
                  {sprint.is_current && <Badge>Bieżący</Badge>}
                </li>
              ))}
            </ul>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
