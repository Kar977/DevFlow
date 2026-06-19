import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";
import { Link } from "react-router-dom";
import { useRegisterMutation } from "@/features/auth/hooks/useRegisterMutation";
import { Button, Input, Label, Card, CardContent, CardHeader, CardTitle } from "@/shared/ui";

const RegisterSchema = z.object({
  full_name: z.string().min(2, "Imię musi mieć co najmniej 2 znaki"),
  email: z.string().email("Podaj poprawny adres e-mail"),
  password: z.string().min(8, "Hasło musi mieć co najmniej 8 znaków"),
});
type RegisterData = z.infer<typeof RegisterSchema>;

export function RegisterForm() {
  const { mutate: register_, isPending, error } = useRegisterMutation();
  const {
    register,
    handleSubmit,
    formState: { errors },
  } = useForm<RegisterData>({
    resolver: zodResolver(RegisterSchema),
  });

  return (
    <Card className="w-full max-w-sm">
      <CardHeader>
        <CardTitle>Utwórz konto</CardTitle>
      </CardHeader>
      <CardContent>
        <form onSubmit={handleSubmit((data) => register_(data))} className="flex flex-col gap-4">
          <div className="flex flex-col gap-1.5">
            <Label htmlFor="full_name">Imię i nazwisko</Label>
            <Input
              id="full_name"
              type="text"
              autoComplete="name"
              {...register("full_name")}
              aria-invalid={!!errors.full_name}
            />
            {errors.full_name && <p className="text-sm text-destructive">{errors.full_name.message}</p>}
          </div>
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
              autoComplete="new-password"
              {...register("password")}
              aria-invalid={!!errors.password}
            />
            {errors.password && <p className="text-sm text-destructive">{errors.password.message}</p>}
          </div>
          {error && (
            <p className="text-sm text-destructive" role="alert">
              Rejestracja nie powiodła się. Spróbuj ponownie.
            </p>
          )}
          <Button type="submit" disabled={isPending} className="w-full">
            {isPending ? "Rejestracja..." : "Zarejestruj się"}
          </Button>
          <p className="text-center text-sm text-muted-foreground">
            Masz już konto?{" "}
            <Link to="/login" className="text-primary underline">
              Zaloguj się
            </Link>
          </p>
        </form>
      </CardContent>
    </Card>
  );
}
