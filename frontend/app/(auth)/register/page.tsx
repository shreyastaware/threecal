import { AuthShell } from "@/features/auth/components/auth-shell";
import { RegisterForm } from "@/features/auth/components/register-form";

export default function RegisterPage() {
  return (
    <AuthShell
      eyebrow="Begin with one link"
      title="Your time has value."
      description="Create an account and shape a booking experience that feels like you."
    >
      <RegisterForm />
    </AuthShell>
  );
}
