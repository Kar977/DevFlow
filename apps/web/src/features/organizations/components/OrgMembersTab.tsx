import { useState } from "react";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";
import { toast } from "sonner";
import {
  Button,
  Card,
  CardContent,
  CardHeader,
  CardTitle,
  Input,
  Label,
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/shared/ui";
import {
  useOrgMembersQuery,
  useInviteMember,
  useRemoveMember,
  useUpdateMemberRole,
} from "@/features/organizations/hooks/useOrgMembers";
import { getErrorMessage } from "@/shared/api/errorMessage";

const InviteSchema = z.object({
  email: z.string().email("Podaj prawidłowy adres email"),
  role: z.enum(["member", "admin", "owner"]),
});
type InviteData = z.infer<typeof InviteSchema>;

const ROLE_OPTIONS = [
  { value: "member", label: "Member" },
  { value: "admin", label: "Admin" },
] as const;

interface Props {
  orgId: string;
  currentUserId: string | undefined;
}

export function OrgMembersTab({ orgId, currentUserId }: Props) {
  const { data: members, isLoading } = useOrgMembersQuery(orgId);
  const inviteMember = useInviteMember(orgId);
  const removeMember = useRemoveMember(orgId);
  const updateRole = useUpdateMemberRole(orgId);

  const [inviteError, setInviteError] = useState<string | null>(null);

  const myRole = members?.find((m) => m.user_id === currentUserId)?.role;
  const isAdmin = myRole === "owner" || myRole === "admin";
  const isOwner = myRole === "owner";

  const {
    register,
    handleSubmit,
    reset,
    setValue,
    watch,
    formState: { errors },
  } = useForm<InviteData>({
    resolver: zodResolver(InviteSchema),
    defaultValues: { role: "member" },
  });
  const currentInviteRole = watch("role");

  function onInvite(data: InviteData) {
    setInviteError(null);
    inviteMember.mutate(
      { email: data.email, role: data.role },
      {
        onSuccess: () => reset(),
        onError: (err) =>
          setInviteError(getErrorMessage(err, "Nie udało się zaprosić użytkownika.")),
      }
    );
  }

  function onRoleChange(userId: string, role: string) {
    updateRole.mutate(
      { userId, role },
      {
        onError: (err) =>
          toast.error(getErrorMessage(err, "Nie udało się zmienić roli.")),
      }
    );
  }

  return (
    <div className="space-y-6">
      {isAdmin && (
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
                <Label>Rola</Label>
                <Select
                  value={currentInviteRole}
                  onValueChange={(v) => setValue("role", v as InviteData["role"])}
                >
                  <SelectTrigger aria-label="Rola">
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    {ROLE_OPTIONS.map((opt) => (
                      <SelectItem key={opt.value} value={opt.value}>
                        {opt.label}
                      </SelectItem>
                    ))}
                    {isOwner && <SelectItem value="owner">Owner</SelectItem>}
                  </SelectContent>
                </Select>
              </div>
              {inviteError && <p className="text-sm text-destructive">{inviteError}</p>}
              <Button type="submit" disabled={inviteMember.isPending} className="self-start">
                {inviteMember.isPending ? "Zapraszanie..." : "Zaproś"}
              </Button>
            </form>
          </CardContent>
        </Card>
      )}

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
                <li key={m.id} className="flex items-center justify-between gap-4 py-3">
                  <p className="text-sm font-medium">{m.display_name}</p>
                  <div className="flex items-center gap-2">
                    <Select
                      value={m.role}
                      disabled={!isAdmin || (m.role === "owner" && !isOwner)}
                      onValueChange={(role) => onRoleChange(m.user_id, role)}
                    >
                      <SelectTrigger
                        className="w-32"
                        aria-label={`Rola: ${m.display_name}`}
                      >
                        <SelectValue />
                      </SelectTrigger>
                      <SelectContent>
                        {ROLE_OPTIONS.map((opt) => (
                          <SelectItem key={opt.value} value={opt.value}>
                            {opt.label}
                          </SelectItem>
                        ))}
                        {(isOwner || m.role === "owner") && (
                          <SelectItem value="owner">Owner</SelectItem>
                        )}
                      </SelectContent>
                    </Select>
                    {m.role !== "owner" && isAdmin && (
                      <Button
                        variant="ghost"
                        size="sm"
                        aria-label={`Usuń członka: ${m.display_name}`}
                        disabled={removeMember.isPending}
                        onClick={() => {
                          if (confirm("Usunąć członka z organizacji?")) {
                            removeMember.mutate(m.user_id);
                          }
                        }}
                      >
                        Usuń
                      </Button>
                    )}
                  </div>
                </li>
              ))}
            </ul>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
