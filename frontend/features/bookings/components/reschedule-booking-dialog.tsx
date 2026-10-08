"use client";

import { Dialog } from "@base-ui/react/dialog";
import { zodResolver } from "@hookform/resolvers/zod";
import { CalendarClock, LoaderCircle, X } from "lucide-react";
import { useEffect } from "react";
import { useForm, useWatch } from "react-hook-form";

import type { Slot } from "@/features/booking/api";
import { SlotPicker } from "@/features/bookings/components/slot-picker";
import { formatWhen } from "@/features/bookings/format";
import { rescheduleBookingSchema, type RescheduleBookingValues } from "@/features/bookings/schemas";
import { StatusMessage } from "@/features/dashboard/components/status-message";
import { getErrorMessage } from "@/lib/api/client";

export function RescheduleBookingDialog({
  open,
  onOpenChange,
  currentLabel,
  durationMinutes,
  slotsQueryKey,
  loadSlots,
  timezone,
  hostTimezone,
  maxDaysInAdvance,
  isPending,
  error,
  onConfirm,
}: {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  /** The booking's current time, already formatted. */
  currentLabel: string;
  durationMinutes: number;
  slotsQueryKey: readonly unknown[];
  loadSlots: (start: string, end: string, timezone: string) => Promise<Slot[]>;
  timezone: string;
  hostTimezone: string;
  maxDaysInAdvance: number | null;
  isPending: boolean;
  error: unknown;
  onConfirm: (startsAt: string) => Promise<unknown>;
}) {
  const { control, setValue, reset, handleSubmit, formState: { errors } } = useForm<RescheduleBookingValues>({
    resolver: zodResolver(rescheduleBookingSchema),
    defaultValues: { starts_at: "" },
  });
  const selected = useWatch({ control, name: "starts_at" });

  useEffect(() => {
    if (!open) reset({ starts_at: "" });
  }, [open, reset]);

  const onSubmit = handleSubmit(async (values) => {
    try {
      await onConfirm(values.starts_at);
    } catch {
      // Surfaced through `error`.
    }
  });

  const selectedEnd = selected ? new Date(new Date(selected).getTime() + durationMinutes * 60_000).toISOString() : null;

  return (
    <Dialog.Root open={open} onOpenChange={(next) => { if (!isPending) onOpenChange(next); }}>
      <Dialog.Portal>
        <Dialog.Backdrop className="profile-dialog-backdrop" />
        <Dialog.Viewport className="profile-dialog-viewport">
          <Dialog.Popup className="profile-dialog-popup reschedule-dialog-popup">
            <div className="profile-dialog-header">
              <div>
                <p className="kicker kicker-dark">Reschedule</p>
                <Dialog.Title>Pick a new time</Dialog.Title>
                <Dialog.Description>Currently {currentLabel}. Times are shown in {timezone}.</Dialog.Description>
              </div>
              <Dialog.Close aria-label="Close reschedule dialog" className="profile-dialog-close" disabled={isPending}>
                <X size={16} />
              </Dialog.Close>
            </div>
            <form className="profile-dialog-form" noValidate onSubmit={onSubmit}>
              {open && (
                <SlotPicker
                  queryKey={slotsQueryKey}
                  loadSlots={loadSlots}
                  timezone={timezone}
                  hostTimezone={hostTimezone}
                  maxDaysInAdvance={maxDaysInAdvance}
                  selected={selected || null}
                  onSelect={(startsAt) => setValue("starts_at", startsAt, { shouldValidate: true })}
                />
              )}
              {selected && selectedEnd && <StatusMessage tone="notice">New time: {formatWhen(selected, selectedEnd, timezone)}</StatusMessage>}
              {errors.starts_at && <small className="field-error">{errors.starts_at.message}</small>}
              {Boolean(error) && <StatusMessage>{getErrorMessage(error)}</StatusMessage>}
              <div className="profile-dialog-actions">
                <Dialog.Close className="profile-dialog-cancel" disabled={isPending}>Keep current time</Dialog.Close>
                <button className="save-button" type="submit" disabled={isPending || !selected}>
                  {isPending ? <LoaderCircle className="spin" size={16} /> : <CalendarClock size={16} />}
                  {isPending ? "Rescheduling" : "Confirm new time"}
                </button>
              </div>
            </form>
          </Dialog.Popup>
        </Dialog.Viewport>
      </Dialog.Portal>
    </Dialog.Root>
  );
}
