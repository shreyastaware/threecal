import { AuthShell } from "@/features/auth/components/auth-shell";
import { ForgotPasswordForm } from "@/features/auth/components/forgot-password-form";

export default function ForgotPasswordPage() {
  return (
    <AuthShell
      eyebrow="Account recovery"
      title="Lost the key?"
      description="Enter the email you signed up with and we will send a link to choose a new password."
    >
      <ForgotPasswordForm />
    </AuthShell>
  );
}
