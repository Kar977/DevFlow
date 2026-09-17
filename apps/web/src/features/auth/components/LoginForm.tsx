import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";
import { Link } from "react-router-dom";
import { Info } from "lucide-react";
import { useLoginMutation } from "@/features/auth/hooks/useLoginMutation";
import { Button, Input, Label, Card, CardContent, CardHeader, CardTitle } from "@/shared/ui";
import {
  DEMO_COLD_START_MESSAGE,
  DEMO_CREDENTIALS,
  DEMO_INTRO_GITHUB_NOTE,
  DEMO_INTRO_MESSAGE,
  DEMO_INTRO_TITLE,
  DEMO_LOGIN_ERROR_MESSAGE,
  IS_DEMO,
} from "@/shared/lib/demo";

const LoginSchema = z.object({
  email: z.string().email("Podaj poprawny adres e-mail"),
  password: z.string().min(1, "Hasło jest wymagane"),
});
type LoginData = z.infer<typeof LoginSchema>;

/**
 * Public showcase entry point — the only thing a demo visitor sees at
 * `/login`. Replaces the regular email/password form entirely (nobody
 * but the shared demo account has credentials, and registration is
 * rejected by the read-only API anyway).
 */
function DemoLoginCard() {
  const { mutate: login, isPending, error } = useLoginMutation();

  return (
    <Card className="w-full max-w-md">
      <CardHeader>
        <CardTitle>{DEMO_INTRO_TITLE}</CardTitle>
      </CardHeader>
      <CardContent>
        <div className="flex flex-col gap-4">
          <p className="text-sm text-muted-foreground">{DEMO_INTRO_MESSAGE}</p>
          <p className="text-sm text-muted-foreground">{DEMO_INTRO_GITHUB_NOTE}</p>
          <div
            role="status"
            className="flex items-center gap-3 rounded-lg border border-blue-200 bg-blue-50 p-3 text-sm text-blue-900"
          >
            <Info className="h-4 w-4 shrink-0" />
            <p>{DEMO_COLD_START_MESSAGE}</p>
          </div>
          <Button
            type="button"
            className="w-full"
            disabled={isPending}
            onClick={() => login(DEMO_CREDENTIALS)}
          >
            {isPending ? "Logowanie..." : "Wejdź do demo"}
          </Button>
          {error && (
            <p className="text-sm text-destructive" role="alert">
              {DEMO_LOGIN_ERROR_MESSAGE}
            </p>
          )}
        </div>
      </CardContent>
    </Card>
  );
}

export function LoginForm() {
  if (IS_DEMO) return <DemoLoginCard />;

  return <RegularLoginForm />;
}

function RegularLoginForm() {
  const { mutate: login, isPending, error } = useLoginMutation();
  const {
    register,
    handleSubmit,
    formState: { errors },
  } = useForm<LoginData>({
    resolver: zodResolver(LoginSchema),
  });

  return (
    <Card className="w-full max-w-sm">
      <CardHeader>
        <CardTitle>Zaloguj się</CardTitle>
      </CardHeader>
      <CardContent>
        <form onSubmit={handleSubmit((data) => login(data))} className="flex flex-col gap-4">
          <div className="flex flex-col gap-1.5">
            <Label htmlFor="email">E-mail</Label>
            <Input
              id="email"
              type="email"
              autoComplete="email"
              {...register("email")}
              aria-invalid={!!errors.email}
            />
            {errors.email && <p className="text-sm text-destructive">{errors.email.message}</p>}
          </div>
          <div className="flex flex-col gap-1.5">
            <Label htmlFor="password">Hasło</Label>
            <Input
              id="password"
              type="password"
              autoComplete="current-password"
              {...register("password")}
              aria-invalid={!!errors.password}
            />
            {errors.password && (
              <p className="text-sm text-destructive">{errors.password.message}</p>
            )}
          </div>
          {error && (
            <p className="text-sm text-destructive" role="alert">
              Nieprawidłowy e-mail lub hasło.
            </p>
          )}
          <Button type="submit" disabled={isPending} className="w-full">
            {isPending ? "Logowanie..." : "Zaloguj się"}
          </Button>
          <p className="text-center text-sm text-muted-foreground">
            Nie masz konta?{" "}
            <Link to="/register" className="text-primary underline">
              Zarejestruj się
            </Link>
          </p>
        </form>
      </CardContent>
    </Card>
  );
}
