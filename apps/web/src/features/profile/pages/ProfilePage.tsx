import { Card, CardContent, CardHeader, CardTitle } from "@/shared/ui";
import { useAuthStore } from "@/shared/store/authStore";
import { ProfileForm } from "@/features/profile/components/ProfileForm";
import { useProfileMutation } from "@/features/profile/hooks/useProfileMutation";

export function ProfilePage() {
  const user = useAuthStore((s) => s.user);
  const mutation = useProfileMutation();

  if (!user) return <p className="text-muted-foreground">Ładowanie...</p>;

  return (
    <div className="space-y-4">
      <h1 className="text-2xl font-semibold">Profil</h1>
      <Card className="max-w-lg">
        <CardHeader>
          <CardTitle>Dane konta</CardTitle>
        </CardHeader>
        <CardContent className="flex flex-col gap-4">
          <div className="flex flex-col gap-1">
            <span className="text-sm text-muted-foreground">Email</span>
            <span className="font-medium">{user.email}</span>
          </div>
          <ProfileForm
            initialName={user.full_name ?? ""}
            initialAvatarUrl={user.avatar_url ?? ""}
            initialTimezone={user.timezone}
            onSubmit={(data) => mutation.mutate(data)}
            isPending={mutation.isPending}
          />
        </CardContent>
      </Card>
    </div>
  );
}
