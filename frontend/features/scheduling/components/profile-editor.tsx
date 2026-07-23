"use client";

import { useMutation, useQueryClient } from "@tanstack/react-query";
import { zodResolver } from "@hookform/resolvers/zod";
import { Check, LoaderCircle } from "lucide-react";
import posthog from "posthog-js";
import { useEffect } from "react";
import { useForm } from "react-hook-form";

import { StatusMessage } from "@/features/dashboard/components/status-message";
import { CURRENT_USER_KEY } from "@/components/providers/auth-provider";
import type { User } from "@/features/auth/types/auth";
import { schedulingApi } from "@/features/scheduling/api";
import { profileSchema, type ProfileFormValues } from "@/features/scheduling/schemas";
import { getErrorMessage } from "@/lib/api/client";

const TIMEZONES = [
  "UTC",
  "Asia/Kolkata",
  "Asia/Singapore",
  "Australia/Sydney",
  "Europe/London",
  "Europe/Paris",
  "America/New_York",
  "America/Chicago",
  "America/Denver",
  "America/Los_Angeles",
];

export function ProfileEditor({ user, onSaved }: { user: User; onSaved?: (updated: User) => void }) {
  const queryClient = useQueryClient();
  const save = useMutation({
    mutationFn: schedulingApi.updateProfile,
    onSuccess: (updated) => queryClient.setQueryData(CURRENT_USER_KEY, updated),
  });
  const {
    register,
    reset,
    handleSubmit,
    formState: { errors, isDirty, isSubmitting },
  } = useForm<ProfileFormValues>({
    resolver: zodResolver(profileSchema),
    defaultValues: {
      full_name: user.full_name,
      username: user.username ?? "",
      timezone: user.timezone,
      bio: user.bio ?? "",
      avatar_url: user.avatar_url ?? "",
    },
  });

  useEffect(() => {
    reset({
      full_name: user.full_name,
      username: user.username ?? "",
      timezone: user.timezone,
      bio: user.bio ?? "",
      avatar_url: user.avatar_url ?? "",
    });
  }, [reset, user]);

  const onSubmit = handleSubmit(async (values) => {
    const updated = await save.mutateAsync({
      ...values,
      username: values.username || null,
      bio: values.bio || null,
      avatar_url: values.avatar_url || null,
    });
    reset({
      full_name: updated.full_name,
      username: updated.username ?? "",
      timezone: updated.timezone,
      bio: updated.bio ?? "",
      avatar_url: updated.avatar_url ?? "",
    });
    posthog.capture("profile_updated", {
      has_booking_url: Boolean(updated.username),
      timezone: updated.timezone,
      has_bio: Boolean(updated.bio),
      has_avatar: Boolean(updated.avatar_url),
    });
    onSaved?.(updated);
  });

  return (
    <section className="workspace-panel profile-panel">
      <div className="panel-heading">
        <div><span>01 / Profile</span><h2>Your public desk</h2></div>
        <p>This becomes the introduction on your booking page.</p>
      </div>
      <form className="profile-form" onSubmit={onSubmit} noValidate>
        <label>
          <span>Full name</span>
          <input autoComplete="name" {...register("full_name")} />
          {errors.full_name && <small className="field-error">{errors.full_name.message}</small>}
        </label>
        <label>
          <span>Booking URL</span>
          <div className="url-input">
            <small>threecal.com/</small>
            <input autoCapitalize="none" autoComplete="username" {...register("username")} />
          </div>
          {errors.username && <small className="field-error">{errors.username.message}</small>}
        </label>
        <label>
          <span>Timezone</span>
          <select {...register("timezone")}>
            {!TIMEZONES.includes(user.timezone) && <option value={user.timezone}>{user.timezone}</option>}
            {TIMEZONES.map((timezone) => <option key={timezone} value={timezone}>{timezone}</option>)}
          </select>
          {errors.timezone && <small className="field-error">{errors.timezone.message}</small>}
        </label>
        <label>
          <span>Profile image URL</span>
          <input type="url" placeholder="https://..." {...register("avatar_url")} />
          {errors.avatar_url && <small className="field-error">{errors.avatar_url.message}</small>}
        </label>
        <label className="bio-field">
          <span>Short bio</span>
          <textarea {...register("bio")} />
          {errors.bio && <small className="field-error">{errors.bio.message}</small>}
        </label>
        {save.isError && <StatusMessage>{getErrorMessage(save.error)}</StatusMessage>}
        {save.isSuccess && !isDirty && <StatusMessage tone="success">Profile saved.</StatusMessage>}
        <button className="save-button" type="submit" disabled={isSubmitting || save.isPending}>
          {save.isPending ? <LoaderCircle className="spin" size={16} /> : <Check size={16} />}
          {save.isPending ? "Saving" : "Save profile"}
        </button>
      </form>
    </section>
  );
}
