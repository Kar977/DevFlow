import { useNavigate } from "react-router-dom";
import { Card, CardContent, CardHeader, CardTitle } from "@/shared/ui";
import type { Project } from "@/features/projects/hooks/useProjectsQuery";

interface Props {
  project: Project;
}

export function ProjectCard({ project }: Props) {
  const navigate = useNavigate();

  return (
    <Card
      className="cursor-pointer hover:bg-accent/50 transition-colors"
      onClick={() => void navigate(`/projects/${project.id}`)}
    >
      <CardHeader>
        <div className="flex items-center justify-between">
          <CardTitle className="text-base">{project.name}</CardTitle>
          <span
            className={`rounded-full px-2 py-0.5 text-xs font-medium ${
              project.status === "active"
                ? "bg-green-100 text-green-700"
                : "bg-slate-100 text-slate-700"
            }`}
          >
            {project.status === "active" ? "Aktywny" : "Zarchiwizowany"}
          </span>
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
