import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { ProjectCard } from "@/features/projects/components/ProjectCard";
import type { Project } from "@/features/projects/hooks/useProjectsQuery";

const baseProject: Project = {
  id: "p1",
  name: "Alpha",
  status: "active",
  org_id: "org1",
  created_by: "u1",
  created_at: "2024-01-01",
  updated_at: "2024-01-01",
};

function renderCard(project: Project) {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={qc}>
      <MemoryRouter>
        <ProjectCard project={project} />
      </MemoryRouter>
    </QueryClientProvider>
  );
}

describe("ProjectCard", () => {
  it("shows an actions menu for an active project", () => {
    renderCard(baseProject);
    expect(screen.getByRole("button", { name: /akcje projektu/i })).toBeInTheDocument();
  });

  it("hides the actions menu for an archived project", () => {
    renderCard({ ...baseProject, status: "archived" });
    expect(screen.queryByRole("button", { name: /akcje projektu/i })).not.toBeInTheDocument();
  });
});
