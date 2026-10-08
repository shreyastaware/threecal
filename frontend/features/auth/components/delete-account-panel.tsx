"use client";

import { Dialog } from "@base-ui/react/dialog";
import { zodResolver } from "@hookform/resolvers/zod";
import { useMutation } from "@tanstack/react-query";
import { LoaderCircle, Trash2, X } from "lucide-react";
import { useRouter } from "next/navigation";
import posthog from "posthog-js";
import { useState } from "react";
import { useForm } from "react-hook-form";

import { StatusMessage } from "@/features/dashboard/components/status-message";
import { authApi } from "@/features/auth/api";
import { useAuth } from "@/features/auth/hooks/use-auth";
import {
  deleteAccountSchema,
  type DeleteAccountFormValues,
} from "@/features/auth/schemas/auth";
import { getErrorMessage } from "@/lib/api/client";

export function DeleteAccountPanel() {
  const router = useRouter();
  const { logout } = useAuth();
  const [open, setOpen] = useState(false);
  const remove = useMutation({ mutationFn: authApi.deleteAccount });
  const {
    register,
    reset,
    handleSubmit,
    formState: { errors },
  } = useForm<DeleteAccountFormValues>({
    resolver: zodResolver(deleteAccountSchema),
    defaultValues: { password: "" },
  });

  function changeOpen(next: boolean) {
    if (remove.isPending) return;
    setOpen(next);
    if (!next) {
      reset({ password: "" });
      remove.reset();
    }
  }

  const onSubmit = handleSubmit(async (values) => {
    try {
      await remove.mutateAsync(values);
    } catch {
      // Surfaced through remove.error in the dialog.
      return;
    }
    posthog.capture("account_deleted");
    // The server already cleared the cookie; this clears cached client state.
    await logout().catch(() => undefined);
    router.replace("/");
  });

  return (
    <section className="workspace-panel settings-panel settings-danger">
      <div className="panel-heading">
        <div><span>03 / Danger zone</span><h2>Delete account</h2></div>
        <p>Permanently removes your profile, event types, availability, booking history, and payment settings.</p>
      </div>
      <div className="settings-danger-body">
        <p className="form-hint">
          Cancel any upcoming confirmed bookings first. This cannot be undone.
        </p>
        <button className="danger-button" type="button" onClick={() => changeOpen(true)}>
          <Trash2 size={16} /> Delete my account
        </button>
      </div>

      <Dialog.Root open={open} onOpenChange={changeOpen}>
        <Dialog.Portal>
          <Dialog.Backdrop className="profile-dialog-backdrop" />
          <Dialog.Viewport className="profile-dialog-viewport">
            <Dialog.Popup className="profile-dialog-popup">
              <div className="profile-dialog-header">
                <div>
                  <p className="kicker kicker-dark">Danger zone</p>
                  <Dialog.Title>Delete your account?</Dialog.Title>
                  <Dialog.Description>
                    Your booking page stops working immediately and all of your data is removed. Enter your password to confirm.
                  </Dialog.Description>
                </div>
                <Dialog.Close
                  aria-label="Close delete account dialog"
                  className="profile-dialog-close"
                  disabled={remove.isPending}
                >
                  <X size={16} />
                </Dialog.Close>
              </div>
              <form className="profile-dialog-form" noValidate onSubmit={onSubmit}>
                <label>
                  <span>Password</span>
                  <input type="password" autoComplete="current-password" autoFocus {...register("password")} />
                  {errors.password && <small className="field-error">{errors.password.message}</small>}
                </label>
                {remove.isError && <StatusMessage>{getErrorMessage(remove.error)}</StatusMessage>}
                <div className="profile-dialog-actions">
                  <Dialog.Close className="profile-dialog-cancel" disabled={remove.isPending}>
                    Keep my account
                  </Dialog.Close>
                  <button className="danger-button" type="submit" disabled={remove.isPending}>
                    {remove.isPending ? <LoaderCircle className="spin" size={16} /> : <Trash2 size={16} />}
                    {remove.isPending ? "Deleting" : "Delete permanently"}
                  </button>
                </div>
              </form>
            </Dialog.Popup>
          </Dialog.Viewport>
        </Dialog.Portal>
      </Dialog.Root>
    </section>
  );
}
