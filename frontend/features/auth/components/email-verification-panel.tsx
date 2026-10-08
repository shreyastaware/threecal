"use client";

import { BadgeCheck, LoaderCircle, Send } from "lucide-react";

import { StatusMessage } from "@/features/dashboard/components/status-message";
import { useResendVerification } from "@/features/auth/hooks/use-resend-verification";
import type { User } from "@/features/auth/types/auth";
import { getErrorMessage } from "@/lib/api/client";

export function EmailVerificationPanel({ user }: { user: User }) {
  const resend = useResendVerification();

  return (
    <section className="workspace-panel settings-panel">
      <div className="panel-heading">
        <div><span>01 / Email</span><h2>Sign-in email</h2></div>
        <p>Used to sign in, recover your password, and receive booking notifications.</p>
      </div>
      <div className="settings-email">
        <div className="settings-email-row">
          <strong>{user.email}</strong>
          {user.is_email_verified ? (
            <span className="settings-badge verified"><BadgeCheck size={14} /> Verified</span>
          ) : (
            <span className="settings-badge pending">Not verified</span>
          )}
        </div>
        {!user.is_email_verified && (
          <>
            <p className="form-hint">
              Open the link we emailed you. Links expire after 48 hours; requesting a new one replaces the old link.
            </p>
            {resend.isError && <StatusMessage>{getErrorMessage(resend.error)}</StatusMessage>}
            {resend.isSuccess && <StatusMessage tone="success">Verification email sent.</StatusMessage>}
            <button
              className="save-button"
              type="button"
              onClick={() => resend.mutate()}
              disabled={resend.isPending}
            >
              {resend.isPending ? <LoaderCircle className="spin" size={16} /> : <Send size={16} />}
              {resend.isPending ? "Sending" : "Resend verification email"}
            </button>
          </>
        )}
      </div>
    </section>
  );
}
