import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";
import { Link } from "react-router-dom";
import { useLoginMutation } from "@/features/auth/hooks/useLoginMutation";
import { Button, Input, Label, Card, CardContent, CardHeader, CardTitle } from "@/shared/ui";

const LoginSchema = z.object({
  email: z.string().email("Podaj poprawny adres e-mail"),
  password: z.string().min(1, "Hasło jest wymagane"),
});
type LoginData = z.infer<typeof LoginSchema>;

export function LoginForm() {
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
            {errors.password && <p className="text-sm text-destructive">{errors.password.message}</p>}
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
