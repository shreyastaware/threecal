"use client";

import { LoaderCircle, MailWarning } from "lucide-react";

import { useResendVerification } from "@/features/auth/hooks/use-resend-verification";
import { getErrorMessage } from "@/lib/api/client";

/** Persistent until the email is verified; intentionally has no dismiss control. */
export function EmailVerificationBanner({ email }: { email: string }) {
  const resend = useResendVerification();

  return (
    <div className="verify-banner" role="status">
      <MailWarning aria-hidden="true" size={18} />
      <p>
        {resend.isSuccess ? (
          <>A fresh verification link is on its way to <strong>{email}</strong>.</>
        ) : resend.isError ? (
          getErrorMessage(resend.error, "We could not send the email.")
        ) : (
          <>Confirm <strong>{email}</strong> to keep your account recoverable.</>
        )}
      </p>
      <button
        type="button"
        onClick={() => resend.mutate()}
        disabled={resend.isPending}
      >
        {resend.isPending && <LoaderCircle className="spin" size={14} />}
        {resend.isSuccess ? "Send again" : "Resend email"}
      </button>
    </div>
  );
}
