"use client";

import { useMutation, useQueryClient } from "@tanstack/react-query";
import { ArrowRight, LoaderCircle } from "lucide-react";
import Link from "next/link";
import { useEffect, useRef } from "react";

import { CURRENT_USER_KEY } from "@/components/providers/auth-provider";
import { authApi } from "@/features/auth/api";
import { getErrorMessage } from "@/lib/api/client";

export function VerifyEmailStatus({ token }: { token: string | null }) {
  const queryClient = useQueryClient();
  const requested = useRef(false);
  const verify = useMutation({
    mutationFn: authApi.verifyEmail,
    // The token may belong to a different account than this browser's session.
    onSuccess: () => queryClient.invalidateQueries({ queryKey: CURRENT_USER_KEY }),
  });
  const { mutate } = verify;

  useEffect(() => {
    // Tokens are single-use, so guard against Strict Mode's double effect run.
    if (!token || requested.current) return;
    requested.current = true;
    mutate(token);
  }, [mutate, token]);

  if (!token) {
    return (
      <div className="auth-form">
        <p className="form-error">
          This verification link is missing its token. Open the link from your
          email again, or request a new one from your dashboard settings.
        </p>
        <p className="auth-switch">
          <Link href="/dashboard/settings">Go to settings</Link>
        </p>
      </div>
    );
  }

  if (verify.isError) {
    return (
      <div className="auth-form">
        <p className="form-error">
          {getErrorMessage(verify.error, "We could not verify your email.")}
        </p>
        <p className="auth-switch">
          Need a fresh link?{" "}
          <Link href="/dashboard/settings">Resend from settings</Link>
        </p>
      </div>
    );
  }

  if (verify.isSuccess) {
    return (
      <div className="auth-form">
        <p className="form-success" role="status">
          {verify.data.email} is verified. You are all set.
        </p>
        <Link className="auth-submit" href="/dashboard">
          Open dashboard <ArrowRight size={18} />
        </Link>
      </div>
    );
  }

  return (
    <div className="auth-form">
      <p className="form-pending" role="status">
        <LoaderCircle className="spin" size={18} /> Confirming your email
        address
      </p>
    </div>
  );
}
