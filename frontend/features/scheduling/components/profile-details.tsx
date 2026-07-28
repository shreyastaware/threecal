"use client";

import { Dialog } from "@base-ui/react/dialog";
import { zodResolver } from "@hookform/resolvers/zod";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import {
  AtSign,
  Check,
  Clock3,
  ExternalLink,
  LoaderCircle,
  Pencil,
  UserRound,
  X,
} from "lucide-react";
import posthog from "posthog-js";
import { useMemo, useState } from "react";
import { useForm } from "react-hook-form";
import { z } from "zod";

import { CURRENT_USER_KEY } from "@/components/providers/auth-provider";
import { TimezoneOptions } from "@/components/timezone-options";
import { StatusMessage } from "@/features/dashboard/components/status-message";
import type { User } from "@/features/auth/types/auth";
import {
  schedulingApi,
  type ProfileUpdate,
} from "@/features/scheduling/api";
import { ProfileImageField } from "@/features/scheduling/components/profile-image-field";
import { profileSchema } from "@/features/scheduling/schemas";
import { getErrorMessage } from "@/lib/api/client";
import { getTimezoneOptionLabel } from "@/lib/timezones";

type ProfileField = keyof Pick<
  User,
  "full_name" | "username" | "timezone" | "bio"
>;

type FieldFormValues = {
  value: string;
};

const fieldSchemas = {
  full_name: profileSchema.shape.full_name,
  username: profileSchema.shape.username,
  timezone: profileSchema.shape.timezone,
  bio: profileSchema.shape.bio,
};

const fieldCopy: Record<
  ProfileField,
  {
    label: string;
    title: string;
    description: string;
    placeholder?: string;
    icon: typeof UserRound;
    inputMode: "input" | "textarea" | "select";
  }
> = {
  full_name: {
    label: "Full name",
    title: "Edit your full name",
    description: "This is the name invitees see on your booking page.",
    placeholder: "Your full name",
    icon: UserRound,
    inputMode: "input",
  },
  username: {
    label: "Booking URL",
    title: "Edit your booking URL",
    description: "Use lowercase letters, numbers, hyphens, or underscores.",
    placeholder: "your-name",
    icon: AtSign,
    inputMode: "input",
  },
  bio: {
    label: "Short bio",
    title: "Edit your short bio",
    description: "Give invitees a concise introduction before they book.",
    placeholder: "Tell invitees a little about your work.",
    icon: Pencil,
    inputMode: "textarea",
  },  
  timezone: {
    label: "Timezone",
    title: "Edit your timezone",
    description: "Your availability and booking times are anchored here.",
    icon: Clock3,
    inputMode: "select",
  },
};

const dialogSchema = z.object({
  value: z.string(),
});

function fieldValue(user: User, field: ProfileField): string {
  return user[field] ?? "";
}

function displayValue(user: User, field: ProfileField): string {
  const value = fieldValue(user, field);
  if (!value) {
    return field === "username" ? "Choose a booking URL" : "Not added yet";
  }
  if (field === "username") return `threecal.com/${value}`;
  if (field === "timezone") return getTimezoneOptionLabel(value);
  return value;
}

function initials(name: string): string {
  return name
    .trim()
    .split(/\s+/)
    .slice(0, 2)
    .map((part) => part.charAt(0).toUpperCase())
    .join("");
}

export function ProfileDetails({ user }: { user: User }) {
  const queryClient = useQueryClient();
  const [activeField, setActiveField] = useState<ProfileField | null>(null);
  const activeCopy = activeField ? fieldCopy[activeField] : null;
  const validationSchema = useMemo(
    () =>
      z.object({
        value: activeField ? fieldSchemas[activeField] : z.string(),
      }),
    [activeField],
  );
  const save = useMutation({
    mutationFn: schedulingApi.updateProfile,
    onSuccess: (updated) => {
      queryClient.setQueryData(CURRENT_USER_KEY, updated);
    },
  });
  const {
    register,
    reset,
    handleSubmit,
    setError,
    formState: { errors, isDirty },
  } = useForm<FieldFormValues>({
    resolver: zodResolver(dialogSchema),
    defaultValues: { value: "" },
  });

  function openEditor(field: ProfileField) {
    save.reset();
    setActiveField(field);
    reset({ value: fieldValue(user, field) });
  }

  function closeEditor() {
    if (save.isPending) return;
    setActiveField(null);
    reset({ value: "" });
    save.reset();
  }

  const onSubmit = handleSubmit(async (values) => {
    if (!activeField) return;

    const result = validationSchema.safeParse(values);
    if (!result.success) {
      setError("value", {
        message: result.error.issues[0]?.message ?? "Enter a valid value",
      });
      return;
    }

    const nullableField = activeField === "username" || activeField === "bio";
    const nextValue =
      nullableField && result.data.value === "" ? null : result.data.value;
    const updated = await save.mutateAsync({
      [activeField]: nextValue,
    } as ProfileUpdate);

    posthog.capture("profile_field_updated", { field: activeField });
    queryClient.setQueryData(CURRENT_USER_KEY, updated);
    setActiveField(null);
  });

  const fields: ProfileField[] = ["full_name", "username", "timezone", "bio"];

  return (
    <>
      <section className="workspace-panel profile-details-panel">
        <div className="panel-heading">
          <div>
            <span>01 / Public profile</span>
            <h2>Your public desk</h2>
          </div>
          <p>
            Review the details invitees see. Open only the field you want to
            change.
          </p>
        </div>

        <div className="profile-details">
          <div className="profile-identity-card">
            <div className="profile-avatar" aria-hidden="true">
              {user.avatar_url ? (
                // eslint-disable-next-line @next/next/no-img-element
                <img alt="" src={user.avatar_url} />
              ) : (
                <span>{initials(user.full_name)}</span>
              )}
            </div>
            <div>
              <strong>{user.full_name}</strong>
              <p>{user.email}</p>
            </div>
            <span className="profile-verified">
              <Check size={13} />{" "}
              {user.is_email_verified ? "Email verified" : "Verification pending"}
            </span>
          </div>

          <div className="profile-field-list">
            <ProfileImageField user={user} />
            {fields.map((field) => {
              const copy = fieldCopy[field];
              const Icon = copy.icon;
              return (
                <article className="profile-field-row" key={field}>
                  <Icon aria-hidden="true" size={17} />
                  <div>
                    <span>{copy.label}</span>
                    <p
                      className={
                        field === "bio"
                          ? "profile-bio-value"
                          : field === "timezone"
                            ? "profile-timezone-value"
                            : ""
                      }
                    >
                      {displayValue(user, field)}
                    </p>
                  </div>
                  <div className="profile-field-actions">
                    {field === "username" && user.username && (
                      <a
                        aria-label="Open booking URL in a new tab"
                        className="profile-open-link"
                        href={`/${encodeURIComponent(user.username)}`}
                        rel="noopener noreferrer"
                        target="_blank"
                        title="Open booking URL"
                      >
                        <ExternalLink size={15} />
                      </a>
                    )}
                    <button
                      aria-label={`Edit ${copy.label.toLowerCase()}`}
                      className="profile-edit-button"
                      onClick={() => openEditor(field)}
                      type="button"
                    >
                      <Pencil size={14} /> Edit
                    </button>
                  </div>
                </article>
              );
            })}
          </div>
        </div>
      </section>

      <Dialog.Root
        onOpenChange={(open) => {
          if (!open) closeEditor();
        }}
        open={activeField !== null}
      >
        <Dialog.Portal>
          <Dialog.Backdrop className="profile-dialog-backdrop" />
          <Dialog.Viewport className="profile-dialog-viewport">
            <Dialog.Popup className="profile-dialog-popup">
              <div className="profile-dialog-header">
                <div>
                  <p className="kicker kicker-dark">Profile detail</p>
                  <Dialog.Title>{activeCopy?.title}</Dialog.Title>
                  <Dialog.Description>
                    {activeCopy?.description}
                  </Dialog.Description>
                </div>
                <Dialog.Close
                  aria-label="Close edit dialog"
                  className="profile-dialog-close"
                  disabled={save.isPending}
                >
                  <X size={18} />
                </Dialog.Close>
              </div>

              <form className="profile-dialog-form" noValidate onSubmit={onSubmit}>
                <label>
                  <span>{activeCopy?.label}</span>
                  {activeField === "username" && (
                    <div className="profile-dialog-url">
                      <small>threecal.com/</small>
                      <input
                        autoCapitalize="none"
                        autoComplete="username"
                        placeholder={activeCopy?.placeholder}
                        {...register("value")}
                      />
                    </div>
                  )}
                  {activeField &&
                    activeCopy?.inputMode === "input" &&
                    activeField !== "username" && (
                      <input
                        autoComplete={
                          activeField === "full_name" ? "name" : "off"
                        }
                        placeholder={activeCopy.placeholder}
                        type="text"
                        {...register("value")}
                      />
                    )}
                  {activeCopy?.inputMode === "textarea" && (
                    <textarea
                      maxLength={1000}
                      placeholder={activeCopy.placeholder}
                      {...register("value")}
                    />
                  )}
                  {activeCopy?.inputMode === "select" && (
                    <select {...register("value")}>
                      <TimezoneOptions currentTimezone={user.timezone} />
                    </select>
                  )}
                  {errors.value && (
                    <small className="field-error">{errors.value.message}</small>
                  )}
                </label>

                {save.isError && (
                  <StatusMessage>{getErrorMessage(save.error)}</StatusMessage>
                )}

                <div className="profile-dialog-actions">
                  <Dialog.Close
                    className="profile-dialog-cancel"
                    disabled={save.isPending}
                  >
                    Cancel
                  </Dialog.Close>
                  <button
                    className="save-button"
                    disabled={!isDirty || save.isPending}
                    type="submit"
                  >
                    {save.isPending ? (
                      <LoaderCircle className="spin" size={16} />
                    ) : (
                      <Check size={16} />
                    )}
                    {save.isPending ? "Saving" : "Save changes"}
                  </button>
                </div>
              </form>
            </Dialog.Popup>
          </Dialog.Viewport>
        </Dialog.Portal>
      </Dialog.Root>
    </>
  );
}
