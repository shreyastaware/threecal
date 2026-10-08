"use client";

import { Dialog } from "@base-ui/react/dialog";
import { zodResolver } from "@hookform/resolvers/zod";
import { CalendarX2, LoaderCircle, X } from "lucide-react";
import { useEffect } from "react";
import { useForm } from "react-hook-form";

import { cancelBookingSchema, type CancelBookingValues } from "@/features/bookings/schemas";
import { StatusMessage } from "@/features/dashboard/components/status-message";
import { getErrorMessage } from "@/lib/api/client";

export function CancelBookingDialog({
  open,
  onOpenChange,
  summary,
  refundNote,
  reasonLabel = "Reason (shared with the other person)",
  isPending,
  error,
  onConfirm,
}: {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  /** What is being cancelled, e.g. "Intro call with Jamie on Tuesday". */
  summary: string;
  refundNote?: string | null;
  reasonLabel?: string;
  isPending: boolean;
  error: unknown;
  onConfirm: (reason: string) => Promise<unknown>;
}) {
  const { register, reset, handleSubmit, formState: { errors } } = useForm<CancelBookingValues>({
    resolver: zodResolver(cancelBookingSchema),
    defaultValues: { reason: "" },
  });

  useEffect(() => {
    if (!open) reset({ reason: "" });
  }, [open, reset]);

  const onSubmit = handleSubmit(async (values) => {
    try {
      await onConfirm(values.reason);
    } catch {
      // Surfaced through `error`.
    }
  });

  return (
    <Dialog.Root open={open} onOpenChange={(next) => { if (!isPending) onOpenChange(next); }}>
      <Dialog.Portal>
        <Dialog.Backdrop className="profile-dialog-backdrop" />
        <Dialog.Viewport className="profile-dialog-viewport">
          <Dialog.Popup className="profile-dialog-popup">
            <div className="profile-dialog-header">
              <div>
                <p className="kicker kicker-dark">Cancel booking</p>
                <Dialog.Title>Cancel this booking?</Dialog.Title>
                <Dialog.Description>{summary}</Dialog.Description>
              </div>
              <Dialog.Close aria-label="Close cancel dialog" className="profile-dialog-close" disabled={isPending}>
                <X size={16} />
              </Dialog.Close>
            </div>
            <form className="profile-dialog-form" noValidate onSubmit={onSubmit}>
              {refundNote && <StatusMessage tone="notice">{refundNote}</StatusMessage>}
              <label>
                <span>{reasonLabel}</span>
                <textarea placeholder="Optional" {...register("reason")} />
                {errors.reason && <small className="field-error">{errors.reason.message}</small>}
              </label>
              {Boolean(error) && <StatusMessage>{getErrorMessage(error)}</StatusMessage>}
              <div className="profile-dialog-actions">
                <Dialog.Close className="profile-dialog-cancel" disabled={isPending}>Keep booking</Dialog.Close>
                <button className="danger-button" type="submit" disabled={isPending}>
                  {isPending ? <LoaderCircle className="spin" size={16} /> : <CalendarX2 size={16} />}
                  {isPending ? "Cancelling" : "Cancel booking"}
                </button>
              </div>
            </form>
          </Dialog.Popup>
        </Dialog.Viewport>
      </Dialog.Portal>
    </Dialog.Root>
  );
}
