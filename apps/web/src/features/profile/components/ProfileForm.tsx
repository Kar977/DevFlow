import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";
import { Button, Input, Label } from "@/shared/ui";

const ProfileSchema = z.object({
  full_name: z.string().min(2, "Imię musi mieć co najmniej 2 znaki"),
  avatar_url: z.string().url("Nieprawidłowy URL").optional().or(z.literal("")),
});
type ProfileFormData = z.infer<typeof ProfileSchema>;

interface Props {
  initialName: string;
  initialAvatarUrl?: string;
  onSubmit: (data: { full_name: string; avatar_url?: string }) => void;
  isPending?: boolean;
}

export function ProfileForm({ initialName, initialAvatarUrl, onSubmit, isPending }: Props) {
  const {
    register,
    handleSubmit,
    formState: { errors },
  } = useForm<ProfileFormData>({
    resolver: zodResolver(ProfileSchema),
    defaultValues: { full_name: initialName, avatar_url: initialAvatarUrl ?? "" },
  });

  function onValid(data: ProfileFormData) {
    onSubmit({
      full_name: data.full_name,
      avatar_url: data.avatar_url || undefined,
    });
  }

  return (
    <form onSubmit={handleSubmit(onValid)} className="flex flex-col gap-4">
      <div className="flex flex-col gap-1.5">
        <Label htmlFor="full_name">Imię i nazwisko</Label>
        <Input id="full_name" {...register("full_name")} />
        {errors.full_name && (
          <p className="text-sm text-destructive">{errors.full_name.message}</p>
        )}
      </div>
      <div className="flex flex-col gap-1.5">
        <Label htmlFor="avatar_url">URL awatara (opcjonalnie)</Label>
        <Input id="avatar_url" {...register("avatar_url")} placeholder="https://..." />
        {errors.avatar_url && (
          <p className="text-sm text-destructive">{errors.avatar_url.message}</p>
        )}
      </div>
      <Button type="submit" disabled={isPending} className="self-start">
        {isPending ? "Zapisywanie..." : "Zapisz"}
      </Button>
    </form>
  );
}
