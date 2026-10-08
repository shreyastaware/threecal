import type { Slot } from "@/features/booking/api";
import { apiRequest } from "@/lib/api/client";

export type BookingStatus = "pending" | "confirmed" | "cancelled" | "expired";
export type BookingScope = "upcoming" | "past" | "cancelled";
export type BookingActor = "host" | "invitee";

/** A booking as the host sees it in the dashboard. */
export type HostBooking = {
  id: string;
  event_type_id: string;
  event_type_title: string;
  event_type_slug: string;
  duration_minutes: number;
  /** Booking window of the event type in days; null means unlimited. */
  max_days_in_advance: number | null;
  invitee_name: string;
  invitee_email: string;
  invitee_timezone: string;
  notes: string | null;
  starts_at: string;
  ends_at: string;
  status: BookingStatus;
  booking_amount: number;
  currency: string;
  provider_payment_id: string | null;
  refund_status: string | null;
  refunded_at: string | null;
  meeting_url: string | null;
  cancelled_at: string | null;
  cancelled_by: BookingActor | null;
  cancellation_reason: string | null;
  created_at: string;
};

export type HostBookingPage = {
  items: HostBooking[];
  total: number;
  limit: number;
  offset: number;
};

/** A booking as the invitee sees it on the manage-booking page. */
export type InviteeBooking = {
  id: string;
  status: BookingStatus;
  event_type_title: string;
  duration_minutes: number;
  max_days_in_advance: number | null;
  host_name: string;
  host_timezone: string;
  invitee_name: string;
  invitee_email: string;
  invitee_timezone: string;
  notes: string | null;
  starts_at: string;
  ends_at: string;
  meeting_url: string | null;
  booking_amount: number;
  currency: string;
  refund_status: string | null;
  cancelled_by: BookingActor | null;
  cancellation_reason: string | null;
  can_cancel: boolean;
  can_reschedule: boolean;
  change_deadline: string;
  cutoff_hours: number;
};

export type BookingListParams = {
  scope: BookingScope;
  eventTypeId?: string;
  limit?: number;
  offset?: number;
};

function query(params: Record<string, string | number | undefined>) {
  const search = new URLSearchParams();
  Object.entries(params).forEach(([key, value]) => {
    if (value !== undefined && value !== "") search.set(key, String(value));
  });
  return search.toString();
}

export const hostBookingsApi = {
  list: ({ scope, eventTypeId, limit, offset }: BookingListParams) =>
    apiRequest<HostBookingPage>(`/bookings?${query({ scope, event_type_id: eventTypeId, limit, offset })}`),
  get: (id: string) => apiRequest<HostBooking>(`/bookings/${encodeURIComponent(id)}`),
  cancel: (id: string, reason?: string) =>
    apiRequest<HostBooking>(`/bookings/${encodeURIComponent(id)}/cancel`, {
      method: "POST",
      body: JSON.stringify({ reason: reason || null }),
    }),
  reschedule: (id: string, startsAt: string) =>
    apiRequest<HostBooking>(`/bookings/${encodeURIComponent(id)}/reschedule`, {
      method: "POST",
      body: JSON.stringify({ starts_at: startsAt }),
    }),
  slots: (id: string, start: string, end: string, timezone: string) =>
    apiRequest<Slot[]>(`/bookings/${encodeURIComponent(id)}/slots?${query({ start, end, timezone })}`),
};

export const inviteeBookingsApi = {
  get: (id: string, token: string) =>
    apiRequest<InviteeBooking>(`/public/bookings/${encodeURIComponent(id)}?${query({ token })}`),
  cancel: (id: string, token: string, reason?: string) =>
    apiRequest<InviteeBooking>(`/public/bookings/${encodeURIComponent(id)}/cancel`, {
      method: "POST",
      body: JSON.stringify({ token, reason: reason || null }),
    }),
  reschedule: (id: string, token: string, startsAt: string) =>
    apiRequest<InviteeBooking>(`/public/bookings/${encodeURIComponent(id)}/reschedule`, {
      method: "POST",
      body: JSON.stringify({ token, starts_at: startsAt }),
    }),
  slots: (id: string, token: string, start: string, end: string, timezone: string) =>
    apiRequest<Slot[]>(`/public/bookings/${encodeURIComponent(id)}/slots?${query({ token, start, end, timezone })}`),
};
