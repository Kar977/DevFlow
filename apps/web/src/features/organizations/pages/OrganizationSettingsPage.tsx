import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/shared/ui";
import { useOrgStore } from "@/shared/store/orgStore";
import { useAuthStore } from "@/shared/store/authStore";
import { useOrgMembersQuery } from "@/features/organizations/hooks/useOrgMembers";
import { OrgGeneralTab } from "@/features/organizations/components/OrgGeneralTab";
import { OrgMembersTab } from "@/features/organizations/components/OrgMembersTab";
import { GitHubIntegrationPage } from "@/features/github/pages/GitHubIntegrationPage";

export function OrganizationSettingsPage() {
  const { activeOrgId } = useOrgStore();
  const currentUserId = useAuthStore((s) => s.user?.id);
  const { data: members } = useOrgMembersQuery(activeOrgId);
  const myRole = members?.find((m) => m.user_id === currentUserId)?.role;
  const isAdmin = myRole === "owner" || myRole === "admin";

  if (!activeOrgId) {
    return (
      <div className="p-8 text-muted-foreground">
        Wybierz organizację w nagłówku, aby zarządzać jej ustawieniami.
      </div>
    );
  }

  return (
    <div className="mx-auto max-w-2xl space-y-6 p-6">
      <h1 className="text-2xl font-bold">Ustawienia organizacji</h1>

      <Tabs defaultValue="general">
        <TabsList>
          <TabsTrigger value="general">Ogólne</TabsTrigger>
          <TabsTrigger value="members">Członkowie</TabsTrigger>
          <TabsTrigger value="github">GitHub</TabsTrigger>
        </TabsList>

        <TabsContent value="general">
          <OrgGeneralTab orgId={activeOrgId} isAdmin={isAdmin} />
        </TabsContent>

        <TabsContent value="members">
          <OrgMembersTab orgId={activeOrgId} currentUserId={currentUserId} />
        </TabsContent>

        <TabsContent value="github">
          <GitHubIntegrationPage />
        </TabsContent>
      </Tabs>
    </div>
  );
}
