import { useNavigate } from "react-router-dom";
import { MoreVertical } from "lucide-react";
import {
  Card,
  CardContent,
  CardHeader,
  CardTitle,
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@/shared/ui";
import type { Project } from "@/features/projects/hooks/useProjectsQuery";
import { useArchiveProject } from "@/features/projects/hooks/useProjectMutations";

interface Props {
  project: Project;
}

export function ProjectCard({ project }: Props) {
  const navigate = useNavigate();
  const archiveProject = useArchiveProject();

  function handleArchive() {
    if (confirm("Zarchiwizować projekt?")) {
      archiveProject.mutate(project.id);
    }
  }

  return (
    <Card
      className="cursor-pointer hover:bg-accent/50 transition-colors"
      onClick={() => void navigate(`/projects/${project.id}`)}
    >
      <CardHeader>
        <div className="flex items-center justify-between">
          <CardTitle className="text-base">{project.name}</CardTitle>
          <div className="flex items-center gap-1.5">
            <span
              className={`rounded-full px-2 py-0.5 text-xs font-medium ${
                project.status === "active"
                  ? "bg-green-100 text-green-700"
                  : "bg-slate-100 text-slate-700"
              }`}
            >
              {project.status === "active" ? "Aktywny" : "Zarchiwizowany"}
            </span>
            {project.status === "active" && (
              <DropdownMenu>
                <DropdownMenuTrigger asChild>
                  <button
                    aria-label="Akcje projektu"
                    className="rounded p-1 hover:bg-accent focus:outline-none focus:ring-2 focus:ring-ring"
                    onClick={(e) => e.stopPropagation()}
                  >
                    <MoreVertical className="h-4 w-4" />
                  </button>
                </DropdownMenuTrigger>
                <DropdownMenuContent
                  align="end"
                  onClick={(e) => e.stopPropagation()}
                >
                  <DropdownMenuItem onClick={handleArchive} className="text-destructive">
                    Archiwizuj
                  </DropdownMenuItem>
                </DropdownMenuContent>
              </DropdownMenu>
            )}
          </div>
        </div>
      </CardHeader>
      {project.description && (
        <CardContent>
          <p className="text-sm text-muted-foreground line-clamp-2">{project.description}</p>
        </CardContent>
      )}
    </Card>
  );
}
