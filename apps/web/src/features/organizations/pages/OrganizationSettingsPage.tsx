import { useState } from "react";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";
import { Trash2 } from "lucide-react";
import { Button, Card, CardContent, CardHeader, CardTitle, Input, Label } from "@/shared/ui";
import { useOrgStore } from "@/shared/store/orgStore";
import { useOrgsQuery } from "@/features/organizations/hooks/useOrgsQuery";
import {
  useOrgMembersQuery,
  useInviteMember,
  useRemoveMember,
} from "@/features/organizations/hooks/useOrgMembers";

const InviteSchema = z.object({
  email: z.string().email("Podaj prawidłowy adres email"),
  role: z.enum(["member", "admin", "owner"]),
});
type InviteData = z.infer<typeof InviteSchema>;

export function OrganizationSettingsPage() {
  const { activeOrgId } = useOrgStore();
  const { data: orgsData } = useOrgsQuery();
  const { data: members, isLoading } = useOrgMembersQuery(activeOrgId);
  const inviteMember = useInviteMember(activeOrgId ?? "");
  const removeMember = useRemoveMember(activeOrgId ?? "");

  const [inviteError, setInviteError] = useState<string | null>(null);

  const activeOrg = orgsData?.items.find((o) => o.id === activeOrgId);

  const {
    register,
    handleSubmit,
    reset,
    formState: { errors },
  } = useForm<InviteData>({
    resolver: zodResolver(InviteSchema),
    defaultValues: { role: "member" },
  });

  function onInvite(data: InviteData) {
    if (!activeOrgId) return;
    setInviteError(null);
    inviteMember.mutate(
      { email: data.email, role: data.role },
      {
        onSuccess: () => reset(),
        onError: (err: unknown) => {
          const msg =
            err instanceof Error ? err.message : "Nie udało się zaprosić użytkownika.";
          setInviteError(msg);
        },
      }
    );
  }

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

      {activeOrg && (
        <Card>
          <CardHeader>
            <CardTitle>Organizacja</CardTitle>
          </CardHeader>
          <CardContent className="space-y-1">
            <p className="font-medium">{activeOrg.name}</p>
            <p className="text-sm text-muted-foreground">Slug: {activeOrg.slug}</p>
          </CardContent>
        </Card>
      )}

      {/* Invite form */}
      <Card>
        <CardHeader>
          <CardTitle>Zaproś członka</CardTitle>
        </CardHeader>
        <CardContent>
          <form onSubmit={handleSubmit(onInvite)} className="flex flex-col gap-4">
            <div className="flex flex-col gap-1.5">
              <Label htmlFor="invite-email">Email</Label>
              <Input
                id="invite-email"
                type="email"
                placeholder="dev@example.com"
                {...register("email")}
                aria-invalid={!!errors.email}
              />
              {errors.email && (
                <p className="text-sm text-destructive">{errors.email.message}</p>
              )}
            </div>
            <div className="flex flex-col gap-1.5">
              <Label htmlFor="invite-role">Rola</Label>
              <select
                id="invite-role"
                className="flex h-10 w-full rounded-md border border-input bg-background px-3 py-2 text-sm ring-offset-background focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2"
                {...register("role")}
              >
                <option value="member">Member</option>
                <option value="admin">Admin</option>
                <option value="owner">Owner</option>
              </select>
            </div>
            {inviteError && (
              <p className="text-sm text-destructive">{inviteError}</p>
            )}
            <Button type="submit" disabled={inviteMember.isPending} className="self-start">
              {inviteMember.isPending ? "Zapraszanie..." : "Zaproś"}
            </Button>
          </form>
        </CardContent>
      </Card>

      {/* Members list */}
      <Card>
        <CardHeader>
          <CardTitle>Członkowie</CardTitle>
        </CardHeader>
        <CardContent>
          {isLoading ? (
            <p className="text-sm text-muted-foreground">Ładowanie...</p>
          ) : !members?.length ? (
            <p className="text-sm text-muted-foreground">Brak członków.</p>
          ) : (
            <ul className="divide-y divide-border">
              {members.map((m) => (
                <li key={m.id} className="flex items-center justify-between py-3">
                  <div>
                    <p className="text-sm font-medium font-mono">{m.user_id}</p>
                    <p className="text-xs text-muted-foreground capitalize">{m.role}</p>
                  </div>
                  {m.role !== "owner" && (
                    <Button
                      variant="ghost"
                      size="sm"
                      aria-label="Usuń członka"
                      disabled={removeMember.isPending}
                      onClick={() => removeMember.mutate(m.user_id)}
                    >
                      <Trash2 className="h-4 w-4 text-destructive" />
                    </Button>
                  )}
                </li>
              ))}
            </ul>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
