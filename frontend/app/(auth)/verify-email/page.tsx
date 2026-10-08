import { AuthShell } from "@/features/auth/components/auth-shell";
import { VerifyEmailStatus } from "@/features/auth/components/verify-email-status";

export default async function VerifyEmailPage({
  searchParams,
}: {
  searchParams: Promise<{ [key: string]: string | string[] | undefined }>;
}) {
  const { token } = await searchParams;
  return (
    <AuthShell
      eyebrow="Email verification"
      title="One last check."
      description="Confirming your email keeps your account recoverable and your booking notifications delivered."
    >
      <VerifyEmailStatus token={typeof token === "string" ? token : null} />
    </AuthShell>
  );
}
