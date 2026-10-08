"use client";

import { zodResolver } from "@hookform/resolvers/zod";
import { useQueryClient } from "@tanstack/react-query";
import { ArrowRight, LoaderCircle } from "lucide-react";
import Link from "next/link";
import { useState } from "react";
import { useForm } from "react-hook-form";

import { CURRENT_USER_KEY } from "@/components/providers/auth-provider";
import { authApi } from "@/features/auth/api";
import {
  resetPasswordSchema,
  type ResetPasswordFormValues,
} from "@/features/auth/schemas/auth";
import { getErrorMessage } from "@/lib/api/client";

export function ResetPasswordForm({ token }: { token: string | null }) {
  const queryClient = useQueryClient();
  const [serverError, setServerError] = useState<string | null>(null);
  const [isComplete, setIsComplete] = useState(false);
  const {
    register,
    handleSubmit,
    formState: { errors, isSubmitting },
  } = useForm<ResetPasswordFormValues>({
    resolver: zodResolver(resetPasswordSchema),
  });

  const onSubmit = handleSubmit(async ({ new_password }) => {
    if (!token) return;
    setServerError(null);
    try {
      await authApi.resetPassword({ token, new_password });
      // The reset signs out every session, including this browser's.
      queryClient.setQueryData(CURRENT_USER_KEY, null);
      setIsComplete(true);
    } catch (error) {
      setServerError(getErrorMessage(error, "Unable to reset your password right now."));
    }
  });

  if (!token) {
    return (
      <div className="auth-form">
        <p className="form-error">
          This reset link is missing its token. Request a new link to continue.
        </p>
        <p className="auth-switch">
          <Link href="/forgot-password">Request a new link</Link>
        </p>
      </div>
    );
  }

  if (isComplete) {
    return (
      <div className="auth-form">
        <p className="form-success" role="status">
          Your password has been updated. Every other session has been signed
          out.
        </p>
        <Link className="auth-submit" href="/login">
          Sign in <ArrowRight size={18} />
        </Link>
      </div>
    );
  }

  return (
    <form className="auth-form" onSubmit={onSubmit} noValidate>
      <label>
        <span>New password</span>
        <input
          type="password"
          autoComplete="new-password"
          {...register("new_password")}
        />
        {errors.new_password && <small>{errors.new_password.message}</small>}
      </label>
      <label>
        <span>Confirm new password</span>
        <input
          type="password"
          autoComplete="new-password"
          {...register("confirm_password")}
        />
        {errors.confirm_password && (
          <small>{errors.confirm_password.message}</small>
        )}
      </label>
      {serverError && <p className="form-error">{serverError}</p>}
      <button className="auth-submit" type="submit" disabled={isSubmitting}>
        {isSubmitting ? (
          <LoaderCircle className="spin" size={18} />
        ) : (
          "Update password"
        )}
        {!isSubmitting && <ArrowRight size={18} />}
      </button>
      <p className="auth-switch">
        Link expired? <Link href="/forgot-password">Request a new one</Link>
      </p>
    </form>
  );
}
