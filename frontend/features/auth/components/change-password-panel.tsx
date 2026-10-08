"use client";

import { zodResolver } from "@hookform/resolvers/zod";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { Check, LoaderCircle } from "lucide-react";
import posthog from "posthog-js";
import { useForm } from "react-hook-form";

import { CURRENT_USER_KEY } from "@/components/providers/auth-provider";
import { StatusMessage } from "@/features/dashboard/components/status-message";
import { authApi } from "@/features/auth/api";
import {
  changePasswordSchema,
  type ChangePasswordFormValues,
} from "@/features/auth/schemas/auth";
import { getErrorMessage } from "@/lib/api/client";

const EMPTY_VALUES: ChangePasswordFormValues = {
  current_password: "",
  new_password: "",
  confirm_password: "",
};

export function ChangePasswordPanel() {
  const queryClient = useQueryClient();
  const change = useMutation({
    mutationFn: authApi.changePassword,
    onSuccess: (updated) => queryClient.setQueryData(CURRENT_USER_KEY, updated),
  });
  const {
    register,
    reset,
    handleSubmit,
    formState: { errors, isDirty },
  } = useForm<ChangePasswordFormValues>({
    resolver: zodResolver(changePasswordSchema),
    defaultValues: EMPTY_VALUES,
  });

  const onSubmit = handleSubmit(async ({ current_password, new_password }) => {
    try {
      await change.mutateAsync({ current_password, new_password });
      reset(EMPTY_VALUES);
      posthog.capture("password_changed");
    } catch {
      // Surfaced through change.error below.
    }
  });

  return (
    <section className="workspace-panel settings-panel">
      <div className="panel-heading">
        <div><span>02 / Password</span><h2>Change password</h2></div>
        <p>Saving a new password signs out every other device. This browser stays signed in.</p>
      </div>
      <form className="profile-form settings-form" onSubmit={onSubmit} noValidate>
        <label className="settings-form-full">
          <span>Current password</span>
          <input type="password" autoComplete="current-password" {...register("current_password")} />
          {errors.current_password && <small className="field-error">{errors.current_password.message}</small>}
        </label>
        <label>
          <span>New password</span>
          <input type="password" autoComplete="new-password" {...register("new_password")} />
          {errors.new_password && <small className="field-error">{errors.new_password.message}</small>}
        </label>
        <label>
          <span>Confirm new password</span>
          <input type="password" autoComplete="new-password" {...register("confirm_password")} />
          {errors.confirm_password && <small className="field-error">{errors.confirm_password.message}</small>}
        </label>
        {change.isError && <StatusMessage>{getErrorMessage(change.error)}</StatusMessage>}
        {change.isSuccess && !isDirty && <StatusMessage tone="success">Password updated. Other sessions were signed out.</StatusMessage>}
        <button className="save-button" type="submit" disabled={change.isPending}>
          {change.isPending ? <LoaderCircle className="spin" size={16} /> : <Check size={16} />}
          {change.isPending ? "Saving" : "Update password"}
        </button>
      </form>
    </section>
  );
}
