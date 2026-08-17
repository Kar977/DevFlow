import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";
import {
  Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter,
  Button, Label,
  Select, SelectContent, SelectItem, SelectTrigger, SelectValue,
} from "@/shared/ui";
import { useGenerateReport } from "@/features/reports/hooks/useReportMutations";
import { useProjectsQuery } from "@/features/projects/hooks/useProjectsQuery";
import { useOrgStore } from "@/shared/store/orgStore";

const REPORT_TYPES = [
  { value: "weekly_summary", label: "Podsumowanie tygodniowe" },
  { value: "project_status", label: "Status projektu" },
  { value: "productivity_overview", label: "Przegląd produktywności" },
  { value: "pr_flow_weekly", label: "Tygodniowy PR-flow" },
] as const;

export const GenerateSchema = z
  .object({
    type: z.enum([
      "weekly_summary",
      "project_status",
      "productivity_overview",
      "pr_flow_weekly",
    ]),
    project_id: z.string().optional(),
  })
  .refine((d) => d.type !== "project_status" || !!d.project_id, {
    path: ["project_id"],
    message: "Wybierz projekt dla raportu statusu projektu.",
  });
type GenerateData = z.infer<typeof GenerateSchema>;

interface Props {
  open: boolean;
  onClose: () => void;
}

export function GenerateReportModal({ open, onClose }: Props) {
  const generateReport = useGenerateReport();
  const { data: projects } = useProjectsQuery();
  const activeOrgId = useOrgStore((s) => s.activeOrgId);

  const {
    handleSubmit,
    setValue,
    watch,
    reset,
    formState: { errors },
  } = useForm<GenerateData>({
    resolver: zodResolver(GenerateSchema),
    defaultValues: { type: "weekly_summary" },
  });

  const reportType = watch("type");
  const needsProject = reportType === "project_status";
  const needsOrg = reportType === "pr_flow_weekly";
  const orgMissing = needsOrg && !activeOrgId;

  function onSubmit(data: GenerateData) {
    generateReport.mutate(
      {
        type: data.type,
        format: "json",
        project_id: data.project_id,
        organization_id: needsOrg ? (activeOrgId ?? undefined) : undefined,
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
          <DialogTitle>Wygeneruj raport</DialogTitle>
        </DialogHeader>
        <form onSubmit={handleSubmit(onSubmit)} className="flex flex-col gap-4">
          <div className="flex flex-col gap-1.5">
            <Label>Typ raportu</Label>
            <Select
              value={reportType}
              onValueChange={(v) => setValue("type", v as GenerateData["type"])}
            >
              <SelectTrigger>
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                {REPORT_TYPES.map((t) => (
                  <SelectItem key={t.value} value={t.value}>
                    {t.label}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>

          {needsProject && (
            <div className="flex flex-col gap-1.5">
              <Label>Projekt</Label>
              <Select onValueChange={(v) => setValue("project_id", v)}>
                <SelectTrigger>
                  <SelectValue placeholder="Wybierz projekt" />
                </SelectTrigger>
                <SelectContent>
                  {projects?.items.map((p) => (
                    <SelectItem key={p.id} value={p.id}>
                      {p.name}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
              {errors.project_id && (
                <p className="text-sm text-red-500">{errors.project_id.message}</p>
              )}
            </div>
          )}

          {orgMissing && (
            <p className="text-sm text-red-500">
              Wybierz aktywną organizację, aby wygenerować ten raport.
            </p>
          )}

          <DialogFooter>
            <Button type="button" variant="outline" onClick={() => { reset(); onClose(); }}>
              Anuluj
            </Button>
            <Button type="submit" disabled={generateReport.isPending || orgMissing}>
              {generateReport.isPending ? "Generowanie..." : "Generuj"}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}
