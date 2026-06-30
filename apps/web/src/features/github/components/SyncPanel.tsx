import { useState } from "react";
import {
  Button, Card, CardContent, CardHeader, CardTitle,
  Select, SelectContent, SelectItem, SelectTrigger, SelectValue,
} from "@/shared/ui";
import { useProjectsQuery } from "@/features/projects/hooks/useProjectsQuery";

interface SyncResult {
  prs_synced: number;
  reviews_synced: number;
}

interface Props {
  onSync: (projectId: string) => void;
  isSyncing: boolean;
  syncResult?: SyncResult;
}

export function SyncPanel({ onSync, isSyncing, syncResult }: Props) {
  const [selectedProject, setSelectedProject] = useState<string>("");
  const { data: projects } = useProjectsQuery();

  return (
    <Card>
      <CardHeader>
        <CardTitle>Synchronizacja</CardTitle>
      </CardHeader>
      <CardContent className="flex flex-col gap-4">
        <div className="flex gap-3">
          <Select value={selectedProject} onValueChange={setSelectedProject}>
            <SelectTrigger className="flex-1">
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
          <Button
            onClick={() => onSync(selectedProject)}
            disabled={!selectedProject || isSyncing}
          >
            {isSyncing ? "Synchronizowanie..." : "Synchronizuj"}
          </Button>
        </div>
        {syncResult && (
          <p className="text-sm text-muted-foreground">
            Zsynchronizowano: {syncResult.prs_synced} PR-ów, {syncResult.reviews_synced} recenzji
          </p>
        )}
      </CardContent>
    </Card>
  );
}
