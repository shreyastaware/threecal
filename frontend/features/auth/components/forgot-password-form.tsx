"use client";

import { zodResolver } from "@hookform/resolvers/zod";
import { ArrowRight, LoaderCircle } from "lucide-react";
import Link from "next/link";
import { useState } from "react";
import { useForm } from "react-hook-form";

import { authApi } from "@/features/auth/api";
import {
  forgotPasswordSchema,
  type ForgotPasswordFormValues,
} from "@/features/auth/schemas/auth";
import { getErrorMessage } from "@/lib/api/client";

export function ForgotPasswordForm() {
  const [serverError, setServerError] = useState<string | null>(null);
  const [sentTo, setSentTo] = useState<string | null>(null);
  const {
    register,
    handleSubmit,
    formState: { errors, isSubmitting },
  } = useForm<ForgotPasswordFormValues>({
    resolver: zodResolver(forgotPasswordSchema),
  });

  const onSubmit = handleSubmit(async ({ email }) => {
    setServerError(null);
    try {
      await authApi.forgotPassword(email);
      setSentTo(email);
    } catch (error) {
      setServerError(getErrorMessage(error, "Unable to send a reset link right now."));
    }
  });

  if (sentTo) {
    return (
      <div className="auth-form">
        <p className="form-success" role="status">
          If an account exists for <strong>{sentTo}</strong>, a reset link is on
          its way. It expires in 1 hour.
        </p>
        <p className="auth-switch">
          Remembered it? <Link href="/login">Back to sign in</Link>
        </p>
      </div>
    );
  }

  return (
    <form className="auth-form" onSubmit={onSubmit} noValidate>
      <label>
        <span>Email address</span>
        <input type="email" autoComplete="email" {...register("email")} />
        {errors.email && <small>{errors.email.message}</small>}
      </label>
      {serverError && <p className="form-error">{serverError}</p>}
      <button className="auth-submit" type="submit" disabled={isSubmitting}>
        {isSubmitting ? (
          <LoaderCircle className="spin" size={18} />
        ) : (
          "Send reset link"
        )}
        {!isSubmitting && <ArrowRight size={18} />}
      </button>
      <p className="auth-switch">
        Remembered it? <Link href="/login">Back to sign in</Link>
      </p>
    </form>
  );
}
