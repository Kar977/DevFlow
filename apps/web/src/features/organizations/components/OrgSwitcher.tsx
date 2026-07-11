import { useEffect, useState } from "react";
import { Plus } from "lucide-react";
import { useQueryClient } from "@tanstack/react-query";
import { useOrgStore } from "@/shared/store/orgStore";
import { useOrgsQuery } from "@/features/organizations/hooks/useOrgsQuery";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue, Button } from "@/shared/ui";
import { CreateOrganizationModal } from "./CreateOrganizationModal";

export function OrgSwitcher() {
  const { activeOrgId, setActiveOrg } = useOrgStore();
  const { data } = useOrgsQuery();
  const queryClient = useQueryClient();
  const [createOpen, setCreateOpen] = useState(false);

  // Auto-select the first org when none is chosen or the stored id is stale.
  useEffect(() => {
    if (!data?.items.length) return;
    const valid = activeOrgId && data.items.some((o) => o.id === activeOrgId);
    if (!valid) setActiveOrg(data.items[0].id);
  }, [data, activeOrgId, setActiveOrg]);

  function handleOrgChange(orgId: string) {
    setActiveOrg(orgId);
    void queryClient.invalidateQueries();
  }

  return (
    <div className="flex items-center gap-1">
      {data?.items.length ? (
        <Select value={activeOrgId ?? ""} onValueChange={handleOrgChange}>
          <SelectTrigger className="w-48">
            <SelectValue placeholder="Wybierz organizację" />
          </SelectTrigger>
          <SelectContent>
            {data.items.map((org) => (
              <SelectItem key={org.id} value={org.id}>
                {org.name}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
      ) : (
        <span className="text-sm text-muted-foreground">Brak organizacji</span>
      )}

      <Button
        variant="ghost"
        size="sm"
        aria-label="Utwórz organizację"
        onClick={() => setCreateOpen(true)}
      >
        <Plus className="h-4 w-4" />
      </Button>

      <CreateOrganizationModal
        open={createOpen}
        onClose={() => setCreateOpen(false)}
      />
    </div>
  );
}
