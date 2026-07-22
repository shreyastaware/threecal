"use client";

import { zodResolver } from "@hookform/resolvers/zod";
import { ArrowRight, LoaderCircle } from "lucide-react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState } from "react";
import { useForm } from "react-hook-form";

import { useAuth } from "@/features/auth/hooks/use-auth";
import {
  loginSchema,
  type LoginFormValues,
} from "@/features/auth/schemas/auth";
import { getErrorMessage } from "@/lib/api/client";

export function LoginForm() {
  const router = useRouter();
  const { login } = useAuth();
  const [serverError, setServerError] = useState<string | null>(null);
  const {
    register,
    handleSubmit,
    formState: { errors, isSubmitting },
  } = useForm<LoginFormValues>({ resolver: zodResolver(loginSchema) });

  const onSubmit = handleSubmit(async (values) => {
    setServerError(null);
    try {
      const user = await login(values);
      router.replace(user.username ? "/dashboard" : "/onboarding");
    } catch (error) {
      setServerError(getErrorMessage(error, "Unable to sign in right now."));
    }
  });

  return (
    <form className="auth-form" onSubmit={onSubmit} noValidate>
      <label>
        <span>Email address</span>
        <input type="email" autoComplete="email" {...register("email")} />
        {errors.email && <small>{errors.email.message}</small>}
      </label>
      <label>
        <span>Password</span>
        <input
          type="password"
          autoComplete="current-password"
          {...register("password")}
        />
        {errors.password && <small>{errors.password.message}</small>}
      </label>
      {serverError && <p className="form-error">{serverError}</p>}
      <button className="auth-submit" type="submit" disabled={isSubmitting}>
        {isSubmitting ? <LoaderCircle className="spin" size={18} /> : "Sign in"}
        {!isSubmitting && <ArrowRight size={18} />}
      </button>
      <p className="auth-switch">
        New to threecal? <Link href="/register">Create your account</Link>
      </p>
    </form>
  );
}
