import { useForm, Controller } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";
import {
  Button,
  Input,
  Label,
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/shared/ui";
import { listTimezones } from "@/shared/lib/timezones";

const ProfileSchema = z.object({
  full_name: z.string().min(2, "Imię musi mieć co najmniej 2 znaki"),
  avatar_url: z.union([z.literal(""), z.string().url("Nieprawidłowy URL")]).optional(),
  timezone: z.string().optional(),
});
type ProfileFormData = z.infer<typeof ProfileSchema>;

interface Props {
  initialName: string;
  initialAvatarUrl?: string;
  initialTimezone?: string | null;
  onSubmit: (data: { full_name: string; avatar_url?: string; timezone?: string }) => void;
  isPending?: boolean;
}

export function ProfileForm({
  initialName,
  initialAvatarUrl,
  initialTimezone,
  onSubmit,
  isPending,
}: Props) {
  const {
    register,
    handleSubmit,
    control,
    formState: { errors },
  } = useForm<ProfileFormData>({
    resolver: zodResolver(ProfileSchema),
    defaultValues: {
      full_name: initialName,
      avatar_url: initialAvatarUrl ?? "",
      timezone: initialTimezone ?? "",
    },
  });

  function onValid(data: ProfileFormData) {
    onSubmit({
      full_name: data.full_name,
      avatar_url: data.avatar_url || undefined,
      timezone: data.timezone || undefined,
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
      <div className="flex flex-col gap-1.5">
        <Label htmlFor="timezone">Strefa czasowa</Label>
        <Controller
          name="timezone"
          control={control}
          render={({ field }) => (
            <Select value={field.value || ""} onValueChange={field.onChange}>
              <SelectTrigger id="timezone" className="w-full max-w-xs">
                <SelectValue placeholder="Wybierz strefę czasową" />
              </SelectTrigger>
              <SelectContent>
                {listTimezones().map((tz) => (
                  <SelectItem key={tz} value={tz}>
                    {tz}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          )}
        />
        <p className="text-sm text-muted-foreground">
          Używana do grupowania statystyk produktywności wg Twojego lokalnego dnia i
          tygodnia.
        </p>
      </div>
      <Button type="submit" disabled={isPending} className="self-start">
        {isPending ? "Zapisywanie..." : "Zapisz"}
      </Button>
    </form>
  );
}
