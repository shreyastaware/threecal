"use client";

import { Dialog } from "@base-ui/react/dialog";
import { keepPreviousData, useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { ArrowLeft, ArrowRight, CalendarClock, CalendarDays, CalendarX2, Check, ExternalLink, LoaderCircle, Video, X } from "lucide-react";
import posthog from "posthog-js";
import { useState } from "react";

import { useAuth } from "@/features/auth/hooks/use-auth";
import { hostBookingsApi, type BookingScope, type HostBooking } from "@/features/bookings/api";
import { BookingStatusBadge } from "@/features/bookings/components/booking-status-badge";
import { CancelBookingDialog } from "@/features/bookings/components/cancel-booking-dialog";
import { RescheduleBookingDialog } from "@/features/bookings/components/reschedule-booking-dialog";
import {
  dayKey,
  displayStatus,
  formatAmount,
  formatDayLabel,
  formatTimeRange,
  formatWhen,
  isChangeable,
  paymentSummary,
} from "@/features/bookings/format";
import { StatusMessage } from "@/features/dashboard/components/status-message";
import { eventTypesApi } from "@/features/event-types/api";
import { getErrorMessage } from "@/lib/api/client";

const PAGE_SIZE = 20;

/** Query key prefix shared by every host booking list, so one invalidation refreshes them all. */
export const HOST_BOOKINGS_KEY = ["host-bookings"] as const;

const tabs: { scope: BookingScope; label: string; emptyTitle: string; emptyText: string }[] = [
  {
    scope: "upcoming",
    label: "Upcoming",
    emptyTitle: "No upcoming bookings",
    emptyText: "When someone books time with you, their appointment will appear here. Share your booking link to get your next booking.",
  },
  {
    scope: "past",
    label: "Past",
    emptyTitle: "No past bookings yet",
    emptyText: "Completed appointments are kept here for your records.",
  },
  {
    scope: "cancelled",
    label: "Cancelled",
    emptyTitle: "Nothing cancelled",
    emptyText: "Cancelled bookings and unpaid reservations that expired show up here.",
  },
];

type DialogState = "detail" | "cancel" | "reschedule" | null;

function groupByDay(bookings: HostBooking[], timezone: string) {
  const groups: { day: string; label: string; items: HostBooking[] }[] = [];
  bookings.forEach((booking) => {
    const day = dayKey(booking.starts_at, timezone);
    const group = groups.find((item) => item.day === day);
    if (group) group.items.push(booking);
    else groups.push({ day, label: formatDayLabel(booking.starts_at, timezone), items: [booking] });
  });
  return groups;
}

function refundNote(booking: HostBooking) {
  if (booking.status === "pending") return "The invitee has not paid yet. Their reservation is released, and a payment that arrives later is refunded automatically.";
  if (booking.provider_payment_id && booking.booking_amount > 0) {
    return `${booking.invitee_name} will be refunded ${formatAmount(booking.booking_amount, booking.currency)} in full.`;
  }
  return null;
}

export function HostBookings() {
  const { user } = useAuth();
  const queryClient = useQueryClient();
  const timezone = user?.timezone ?? "UTC";
  const [scope, setScope] = useState<BookingScope>("upcoming");
  const [eventTypeId, setEventTypeId] = useState("");
  const [page, setPage] = useState(0);
  const [selected, setSelected] = useState<HostBooking | null>(null);
  const [dialog, setDialog] = useState<DialogState>(null);
  const [notice, setNotice] = useState<string | null>(null);

  const events = useQuery({ queryKey: ["event-types"], queryFn: eventTypesApi.list, enabled: Boolean(user) });
  const bookings = useQuery({
    queryKey: [...HOST_BOOKINGS_KEY, scope, eventTypeId, page],
    queryFn: () => hostBookingsApi.list({ scope, eventTypeId: eventTypeId || undefined, limit: PAGE_SIZE, offset: page * PAGE_SIZE }),
    enabled: Boolean(user),
    placeholderData: keepPreviousData,
  });

  function afterChange(booking: HostBooking, message: string) {
    setSelected(booking);
    setDialog(null);
    setNotice(message);
    void queryClient.invalidateQueries({ queryKey: HOST_BOOKINGS_KEY });
  }

  const cancel = useMutation({
    mutationFn: ({ id, reason }: { id: string; reason: string }) => hostBookingsApi.cancel(id, reason),
    onSuccess: (booking) => {
      posthog.capture("booking_cancelled", { cancelled_by: "host", is_paid: booking.booking_amount > 0 });
      afterChange(booking, booking.refund_status ? `Booking with ${booking.invitee_name} cancelled and refunded.` : `Booking with ${booking.invitee_name} cancelled.`);
    },
  });
  const reschedule = useMutation({
    mutationFn: ({ id, startsAt }: { id: string; startsAt: string }) => hostBookingsApi.reschedule(id, startsAt),
    onSuccess: (booking) => {
      posthog.capture("booking_rescheduled", { rescheduled_by: "host" });
      afterChange(booking, `Booking with ${booking.invitee_name} moved to ${formatWhen(booking.starts_at, booking.ends_at, timezone)}.`);
    },
  });

  function openDetail(booking: HostBooking) {
    setSelected(booking);
    setDialog("detail");
  }

  function changeTab(next: BookingScope) {
    setScope(next);
    setPage(0);
  }

  function openAction(action: "cancel" | "reschedule") {
    cancel.reset();
    reschedule.reset();
    setDialog(action);
  }

  const activeTab = tabs.find((tab) => tab.scope === scope) ?? tabs[0];
  const items = bookings.data?.items ?? [];
  const total = bookings.data?.total ?? 0;
  const groups = groupByDay(items, timezone);
  const first = page * PAGE_SIZE + 1;
  const last = page * PAGE_SIZE + items.length;

  return (
    <>
      <section className="bookings-toolbar">
        <div className="bookings-tabs" role="tablist" aria-label="Booking lists">
          {tabs.map((tab) => (
            <button key={tab.scope} type="button" role="tab" aria-selected={scope === tab.scope} className={scope === tab.scope ? "selected" : ""} onClick={() => changeTab(tab.scope)}>
              {tab.label}
            </button>
          ))}
        </div>
        <label className="bookings-filter">
          <span>Event type</span>
          <select value={eventTypeId} onChange={(event) => { setEventTypeId(event.target.value); setPage(0); }}>
            <option value="">All event types</option>
            {events.data?.map((event) => <option key={event.id} value={event.id}>{event.title}</option>)}
          </select>
        </label>
      </section>
      <p className="bookings-timezone"><CalendarDays size={14}/> Times shown in {timezone}</p>
      {notice && <StatusMessage tone="success"><Check size={15}/> {notice}</StatusMessage>}
      {bookings.isError && <StatusMessage>{getErrorMessage(bookings.error)}</StatusMessage>}
      {bookings.isLoading && <p className="booking-processing"><LoaderCircle className="spin" size={15}/> Loading bookings</p>}

      {!bookings.isLoading && !bookings.isError && !items.length && (
        <section className="empty-feature">
          <CalendarDays aria-hidden="true" size={26} />
          <h2>{activeTab.emptyTitle}</h2>
          <p>{eventTypeId ? "No bookings of this event type here. Try another filter." : activeTab.emptyText}</p>
        </section>
      )}

      <div className="bookings-list" role="tabpanel" aria-busy={bookings.isFetching}>
        {groups.map((group) => (
          <section className="bookings-day" key={group.day}>
            <h2>{group.label}</h2>
            <ul>
              {group.items.map((booking) => (
                <li className="booking-row" key={booking.id}>
                  <button className="booking-row-main" type="button" onClick={() => openDetail(booking)}>
                    <span className="booking-row-time">{formatTimeRange(booking.starts_at, booking.ends_at, timezone)}</span>
                    <span className="booking-row-who">
                      <strong>{booking.invitee_name}</strong>
                      <small>{booking.event_type_title} · {booking.duration_minutes} min</small>
                    </span>
                    <span className="booking-row-payment">{paymentSummary(booking)}</span>
                    <BookingStatusBadge status={displayStatus(booking, scope)} />
                  </button>
                  {booking.meeting_url && booking.status === "confirmed" && (
                    <a className="text-link booking-row-join" href={booking.meeting_url} target="_blank" rel="noreferrer"><Video size={14}/> Join</a>
                  )}
                </li>
              ))}
            </ul>
          </section>
        ))}
      </div>

      {total > PAGE_SIZE && (
        <nav className="slot-window-nav bookings-pagination" aria-label="Booking pages">
          <button type="button" disabled={page === 0} onClick={() => setPage((value) => Math.max(0, value - 1))}><ArrowLeft size={14}/> Previous</button>
          <span>{first}–{last} of {total}</span>
          <button type="button" disabled={last >= total} onClick={() => setPage((value) => value + 1)}>Next <ArrowRight size={14}/></button>
        </nav>
      )}

      {selected && (
        <Dialog.Root open={dialog === "detail"} onOpenChange={(open) => { if (!open) setDialog(null); }}>
          <Dialog.Portal>
            <Dialog.Backdrop className="profile-dialog-backdrop" />
            <Dialog.Viewport className="profile-dialog-viewport">
              <Dialog.Popup className="profile-dialog-popup booking-detail-popup">
                <div className="profile-dialog-header">
                  <div>
                    <p className="kicker kicker-dark">{selected.event_type_title}</p>
                    <Dialog.Title>{selected.invitee_name}</Dialog.Title>
                    <Dialog.Description>{formatWhen(selected.starts_at, selected.ends_at, timezone)}</Dialog.Description>
                  </div>
                  <Dialog.Close aria-label="Close booking details" className="profile-dialog-close"><X size={16} /></Dialog.Close>
                </div>
                <dl className="booking-detail-list">
                  <div><dt>Status</dt><dd><BookingStatusBadge status={displayStatus(selected, scope)} /></dd></div>
                  <div><dt>Invitee</dt><dd>{selected.invitee_name} · <a className="text-link" href={`mailto:${selected.invitee_email}`}>{selected.invitee_email}</a></dd></div>
                  <div><dt>Their time</dt><dd>{formatWhen(selected.starts_at, selected.ends_at, selected.invitee_timezone)} ({selected.invitee_timezone})</dd></div>
                  <div><dt>Payment</dt><dd>{paymentSummary(selected)}</dd></div>
                  {selected.meeting_url && <div><dt>Meeting</dt><dd><a className="text-link" href={selected.meeting_url} target="_blank" rel="noreferrer">{selected.meeting_url} <ExternalLink size={12}/></a></dd></div>}
                  <div><dt>Notes</dt><dd className="booking-detail-notes">{selected.notes || "No notes."}</dd></div>
                  {selected.status === "cancelled" && (
                    <div><dt>Cancelled</dt><dd>By {selected.cancelled_by === "host" ? "you" : selected.cancelled_by === "invitee" ? selected.invitee_name : "the system"}{selected.cancellation_reason ? ` — “${selected.cancellation_reason}”` : ""}</dd></div>
                  )}
                </dl>
                {isChangeable(selected) && (
                  <div className="profile-dialog-actions">
                    {selected.status === "confirmed" && (
                      <button className="profile-dialog-cancel" type="button" onClick={() => openAction("reschedule")}><CalendarClock size={15}/> Reschedule</button>
                    )}
                    <button className="danger-button" type="button" onClick={() => openAction("cancel")}><CalendarX2 size={15}/> Cancel booking</button>
                  </div>
                )}
              </Dialog.Popup>
            </Dialog.Viewport>
          </Dialog.Portal>
        </Dialog.Root>
      )}

      {selected && (
        <CancelBookingDialog
          open={dialog === "cancel"}
          onOpenChange={(open) => setDialog(open ? "cancel" : "detail")}
          summary={`${selected.event_type_title} with ${selected.invitee_name}, ${formatWhen(selected.starts_at, selected.ends_at, timezone)}. ${selected.invitee_name} will be notified by email.`}
          refundNote={refundNote(selected)}
          isPending={cancel.isPending}
          error={cancel.error}
          onConfirm={(reason) => cancel.mutateAsync({ id: selected.id, reason })}
        />
      )}

      {selected && (
        <RescheduleBookingDialog
          open={dialog === "reschedule"}
          onOpenChange={(open) => setDialog(open ? "reschedule" : "detail")}
          currentLabel={formatWhen(selected.starts_at, selected.ends_at, timezone)}
          durationMinutes={selected.duration_minutes}
          slotsQueryKey={["host-booking-slots", selected.id]}
          loadSlots={(start, end, slotTimezone) => hostBookingsApi.slots(selected.id, start, end, slotTimezone)}
          timezone={timezone}
          hostTimezone={timezone}
          maxDaysInAdvance={selected.max_days_in_advance}
          isPending={reschedule.isPending}
          error={reschedule.error}
          onConfirm={(startsAt) => reschedule.mutateAsync({ id: selected.id, startsAt })}
        />
      )}
    </>
  );
}
