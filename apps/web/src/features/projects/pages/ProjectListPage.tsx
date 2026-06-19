import { useState } from "react";
import { Button } from "@/shared/ui";
import { useProjectsQuery } from "@/features/projects/hooks/useProjectsQuery";
import { ProjectCard } from "@/features/projects/components/ProjectCard";
import { CreateProjectModal } from "@/features/projects/components/CreateProjectModal";
import { useOrgStore } from "@/shared/store/orgStore";

export function ProjectListPage() {
  const { activeOrgId } = useOrgStore();
  const [showCreate, setShowCreate] = useState(false);
  const { data, isLoading } = useProjectsQuery();

  if (!activeOrgId) {
    return (
      <div className="space-y-4">
        <h1 className="text-2xl font-semibold">Projekty</h1>
        <p className="text-muted-foreground">Wybierz organizację, aby zobaczyć projekty.</p>
      </div>
    );
  }

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-semibold">Projekty</h1>
        <Button onClick={() => setShowCreate(true)}>Nowy projekt</Button>
      </div>

      {isLoading && <p className="text-muted-foreground">Ładowanie...</p>}

      {data && (
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {data.items.length === 0 && (
            <p className="text-muted-foreground col-span-full py-8 text-center">
              Brak projektów. Utwórz pierwszy!
            </p>
          )}
          {data.items.map((project) => (
            <ProjectCard key={project.id} project={project} />
          ))}
        </div>
      )}

      <CreateProjectModal open={showCreate} onClose={() => setShowCreate(false)} />
    </div>
  );
}
