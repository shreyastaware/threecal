import { AuthShell } from "@/features/auth/components/auth-shell";
import { LoginForm } from "@/features/auth/components/login-form";

export default function LoginPage() {
  return (
    <AuthShell
      eyebrow="Welcome back"
      title="Return to your calendar."
      description="Sign in to manage your sessions and keep your time moving."
    >
      <LoginForm />
    </AuthShell>
  );
}
