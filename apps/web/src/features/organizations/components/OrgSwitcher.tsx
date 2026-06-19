import { useQueryClient } from "@tanstack/react-query";
import { useOrgStore } from "@/shared/store/orgStore";
import { useOrgsQuery } from "@/features/organizations/hooks/useOrgsQuery";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/shared/ui";

export function OrgSwitcher() {
  const { activeOrgId, setActiveOrg } = useOrgStore();
  const { data } = useOrgsQuery();
  const queryClient = useQueryClient();

  if (!data?.items.length) return null;

  function handleOrgChange(orgId: string) {
    setActiveOrg(orgId);
    void queryClient.invalidateQueries();
  }

  return (
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
  );
}
