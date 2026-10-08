import { AuthShell } from "@/features/auth/components/auth-shell";
import { ResetPasswordForm } from "@/features/auth/components/reset-password-form";

export default async function ResetPasswordPage({
  searchParams,
}: {
  searchParams: Promise<{ [key: string]: string | string[] | undefined }>;
}) {
  const { token } = await searchParams;
  return (
    <AuthShell
      eyebrow="Account recovery"
      title="Choose a new password."
      description="Pick something strong. Once saved, every other signed-in session is signed out."
    >
      <ResetPasswordForm token={typeof token === "string" ? token : null} />
    </AuthShell>
  );
}
