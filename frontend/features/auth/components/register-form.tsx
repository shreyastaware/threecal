"use client";

import { zodResolver } from "@hookform/resolvers/zod";
import { ArrowRight, LoaderCircle } from "lucide-react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState } from "react";
import { useForm } from "react-hook-form";

import { useAuth } from "@/features/auth/hooks/use-auth";
import {
  registerSchema,
  type RegisterFormValues,
} from "@/features/auth/schemas/auth";
import { getErrorMessage } from "@/lib/api/client";

export function RegisterForm() {
  const router = useRouter();
  const { register: createAccount } = useAuth();
  const [serverError, setServerError] = useState<string | null>(null);
  const {
    register,
    handleSubmit,
    formState: { errors, isSubmitting },
  } = useForm<RegisterFormValues>({ resolver: zodResolver(registerSchema) });

  const onSubmit = handleSubmit(async (values) => {
    setServerError(null);
    try {
      await createAccount(values);
       router.replace("/onboarding");
    } catch (error) {
      setServerError(getErrorMessage(error, "Unable to create your account right now."));
    }
  });

  return (
    <form className="auth-form" onSubmit={onSubmit} noValidate>
      <label>
        <span>Full name</span>
        <input autoComplete="name" {...register("full_name")} />
        {errors.full_name && <small>{errors.full_name.message}</small>}
      </label>
      <label>
        <span>Email address</span>
        <input type="email" autoComplete="email" {...register("email")} />
        {errors.email && <small>{errors.email.message}</small>}
      </label>
      <label>
        <span>Password</span>
        <input
          type="password"
          autoComplete="new-password"
          {...register("password")}
        />
        {errors.password && <small>{errors.password.message}</small>}
      </label>
      {serverError && <p className="form-error">{serverError}</p>}
      <button className="auth-submit" type="submit" disabled={isSubmitting}>
        {isSubmitting ? (
          <LoaderCircle className="spin" size={18} />
        ) : (
          "Create account"
        )}
        {!isSubmitting && <ArrowRight size={18} />}
      </button>
      <p className="auth-switch">
        Already have an account? <Link href="/login">Sign in</Link>
      </p>
    </form>
  );
}
