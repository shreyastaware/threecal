import { apiRequest } from "@/lib/api/client";

export type PublicHost = {
  full_name: string;
  username: string;
  bio: string | null;
  timezone: string;
  avatar_url: string | null;
};

export type PublicEventType = {
  id: string;
  title: string;
  slug: string;
  description: string | null;
  duration_minutes: number;
  slot_interval_minutes: number;
  price_minor: number;
  currency: string;
  is_active: boolean;
  is_default: boolean;
};

export type PublicPage = {
  host: PublicHost;
  event_type: PublicEventType;
};

export type PublicProfile = {
  host: PublicHost;
  event_types: PublicEventType[];
  default_event_type_slug: string | null;
};

export type Slot = { starts_at: string; ends_at: string };

export type Booking = {
  id: string;
  event_type_id: string;
  invitee_name: string;
  invitee_email: string;
  starts_at: string;
  ends_at: string;
  status: "pending" | "confirmed" | "cancelled" | "expired";
  provider_payment_id: string | null;
  booking_amount: number;
  payment_expires_at: string;
};

export type BookingInput = {
  starts_at: string;
  invitee_name: string;
  invitee_email: string;
  invitee_timezone: string;
  notes?: string;
};

export const bookingApi = {
  getProfile: (username: string) =>
    apiRequest<PublicProfile>(`/public/${encodeURIComponent(username)}`),
  getPage: (username: string, eventSlug: string) =>
    apiRequest<PublicPage>(`/public/${encodeURIComponent(username)}/${encodeURIComponent(eventSlug)}`),
  getSlots: (username: string, eventSlug: string, start: string, end: string, timezone: string) =>
    apiRequest<Slot[]>(`/public/${encodeURIComponent(username)}/${encodeURIComponent(eventSlug)}/slots?start=${start}&end=${end}&timezone=${encodeURIComponent(timezone)}`),
  create: (username: string, eventSlug: string, input: BookingInput) =>
    apiRequest<Booking>(`/public/${encodeURIComponent(username)}/${encodeURIComponent(eventSlug)}/bookings`, {
      method: "POST",
      body: JSON.stringify(input),
    }),
};
