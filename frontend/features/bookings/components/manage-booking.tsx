"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { CalendarClock, CalendarDays, CalendarX2, Check, Clock3, LoaderCircle, Video } from "lucide-react";
import posthog from "posthog-js";
import { useState } from "react";

import { inviteeBookingsApi, type InviteeBooking } from "@/features/bookings/api";
import { BookingStatusBadge } from "@/features/bookings/components/booking-status-badge";
import { CancelBookingDialog } from "@/features/bookings/components/cancel-booking-dialog";
import { RescheduleBookingDialog } from "@/features/bookings/components/reschedule-booking-dialog";
import { displayStatus, formatAmount, formatDateTime, formatWhen, parseUtc } from "@/features/bookings/format";
import { StatusMessage } from "@/features/dashboard/components/status-message";
import { getErrorMessage } from "@/lib/api/client";

function refundSummary(booking: InviteeBooking) {
  if (!booking.booking_amount) return null;
  const amount = formatAmount(booking.booking_amount, booking.currency);
  if (booking.refund_status === "processed") return `${amount} refunded in full.`;
  if (booking.refund_status === "failed") return `The refund of ${amount} could not be completed. Please contact ${booking.host_name}.`;
  if (booking.refund_status) return `A full refund of ${amount} is on its way. It usually arrives within 5–7 business days.`;
  return null;
}

export function ManageBooking({ bookingId, token }: { bookingId: string; token: string | null }) {
  const queryClient = useQueryClient();
  const [dialog, setDialog] = useState<"cancel" | "reschedule" | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  // Snapshot of the time the page was opened; the server enforces the real cutoff.
  const [openedAt] = useState(() => Date.now());
  const queryKey = ["invitee-booking", bookingId, token] as const;
  const booking = useQuery({
    queryKey,
    queryFn: () => inviteeBookingsApi.get(bookingId, token ?? ""),
    enabled: Boolean(token),
    retry: false,
  });

  function applyUpdate(updated: InviteeBooking, message: string) {
    queryClient.setQueryData(queryKey, updated);
    setDialog(null);
    setNotice(message);
  }

  const cancel = useMutation({
    mutationFn: (reason: string) => inviteeBookingsApi.cancel(bookingId, token ?? "", reason),
    onSuccess: (updated) => {
      posthog.capture("booking_cancelled", { cancelled_by: "invitee", is_paid: updated.booking_amount > 0 });
      applyUpdate(updated, "Your booking has been cancelled. We've emailed you a confirmation.");
    },
  });
  const reschedule = useMutation({
    mutationFn: (startsAt: string) => inviteeBookingsApi.reschedule(bookingId, token ?? "", startsAt),
    onSuccess: (updated) => {
      posthog.capture("booking_rescheduled", { rescheduled_by: "invitee" });
      applyUpdate(updated, `Your booking is now ${formatWhen(updated.starts_at, updated.ends_at, updated.invitee_timezone)}. An updated invite is on its way.`);
    },
  });

  if (!token) {
    return <main className="booking-loading"><StatusMessage>This link is incomplete. Open the &ldquo;Manage booking&rdquo; link from your confirmation email again.</StatusMessage></main>;
  }
  if (booking.isLoading) return <main className="booking-loading"><LoaderCircle className="spin"/> Loading your booking</main>;
  if (booking.isError || !booking.data) {
    return <main className="booking-loading"><StatusMessage>{booking.isError ? getErrorMessage(booking.error) : "This booking could not be found."} Check that you opened the latest link from your email.</StatusMessage></main>;
  }

  const data = booking.data;
  const timezone = data.invitee_timezone;
  const when = formatWhen(data.starts_at, data.ends_at, timezone);
  const isConfirmed = data.status === "confirmed";
  const isUpcoming = parseUtc(data.ends_at).getTime() > openedAt;
  const refund = refundSummary(data);

  return (
    <main className="booking-canvas manage-booking-canvas">
      <section className="booking-intro">
        <div><span className="wordmark wordmark-light">threecal.</span><p className="booking-number">MANAGE BOOKING</p></div>
        <div className="host-copy">
          <p className="kicker">Appointment with</p>
          <h1>{data.host_name}</h1>
          <p>Booked by {data.invitee_name} ({data.invitee_email}).</p>
        </div>
        <div className="event-ticket"><span>{data.event_type_title}</span><strong><Clock3/> {data.duration_minutes} min</strong><small>{data.booking_amount ? formatAmount(data.booking_amount, data.currency) : "No payment required"}</small></div>
      </section>
      <section className="slot-desk">
        <header>
          <p className="kicker kicker-dark">Your booking</p>
          <h2>{data.status === "cancelled" ? "Cancelled" : isUpcoming ? "See you soon" : "Completed"}</h2>
          <p><CalendarDays/> Shown in {timezone}</p>
        </header>
        <div className="manage-booking-body">
          {notice && <StatusMessage tone="success"><Check size={15}/> {notice}</StatusMessage>}
          <dl className="booking-detail-list">
            <div><dt>Status</dt><dd><BookingStatusBadge status={displayStatus(data)} /></dd></div>
            <div><dt>When</dt><dd>{when}</dd></div>
            <div><dt>Host time</dt><dd>{formatWhen(data.starts_at, data.ends_at, data.host_timezone)} ({data.host_timezone})</dd></div>
            {data.meeting_url && isConfirmed && <div><dt>Meeting</dt><dd><a className="text-link" href={data.meeting_url} target="_blank" rel="noreferrer"><Video size={14}/> Join meeting</a></dd></div>}
            {data.notes && <div><dt>Your notes</dt><dd className="booking-detail-notes">{data.notes}</dd></div>}
            {data.status === "cancelled" && (
              <div><dt>Cancelled</dt><dd>By {data.cancelled_by === "invitee" ? "you" : data.host_name}{data.cancellation_reason ? ` — “${data.cancellation_reason}”` : ""}</dd></div>
            )}
          </dl>
          {refund && data.status === "cancelled" && <StatusMessage tone="notice">{refund}</StatusMessage>}

          {isConfirmed && isUpcoming && (data.can_cancel || data.can_reschedule) && (
            <>
              <p className="form-hint">You can reschedule or cancel until {formatDateTime(data.change_deadline, timezone)} ({data.cutoff_hours} hours before the start).{data.booking_amount ? " Cancelling gives you a full refund." : ""}</p>
              <div className="manage-booking-actions">
                {data.can_reschedule && <button className="save-button" type="button" onClick={() => { reschedule.reset(); setDialog("reschedule"); }}><CalendarClock size={16}/> Reschedule</button>}
                {data.can_cancel && <button className="danger-button" type="button" onClick={() => { cancel.reset(); setDialog("cancel"); }}><CalendarX2 size={16}/> Cancel booking</button>}
              </div>
            </>
          )}
          {isConfirmed && isUpcoming && !data.can_cancel && !data.can_reschedule && (
            <StatusMessage tone="notice">
              Online changes close {data.cutoff_hours} hours before the start, so this booking can no longer be changed here. Please contact {data.host_name} directly if you need to make a change.
            </StatusMessage>
          )}
          {data.status === "pending" && <StatusMessage tone="notice">This booking is waiting for payment and can&apos;t be changed yet.</StatusMessage>}
        </div>
      </section>

      <CancelBookingDialog
        open={dialog === "cancel"}
        onOpenChange={(open) => setDialog(open ? "cancel" : null)}
        summary={`${data.event_type_title} with ${data.host_name}, ${when}. ${data.host_name} will be notified by email.`}
        refundNote={data.booking_amount ? `You'll receive a full refund of ${formatAmount(data.booking_amount, data.currency)}.` : null}
        reasonLabel={`Message for ${data.host_name}`}
        isPending={cancel.isPending}
        error={cancel.error}
        onConfirm={(reason) => cancel.mutateAsync(reason)}
      />
      <RescheduleBookingDialog
        open={dialog === "reschedule"}
        onOpenChange={(open) => setDialog(open ? "reschedule" : null)}
        currentLabel={when}
        durationMinutes={data.duration_minutes}
        slotsQueryKey={["invitee-booking-slots", bookingId, token]}
        loadSlots={(start, end, slotTimezone) => inviteeBookingsApi.slots(bookingId, token, start, end, slotTimezone)}
        timezone={timezone}
        hostTimezone={data.host_timezone}
        maxDaysInAdvance={data.max_days_in_advance}
        isPending={reschedule.isPending}
        error={reschedule.error}
        onConfirm={(startsAt) => reschedule.mutateAsync(startsAt)}
      />
    </main>
  );
}
