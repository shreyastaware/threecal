import { apiRequest } from "@/lib/api/client";

export type LocationType =
  | "none"
  | "in_person"
  | "phone"
  | "custom_link"
  | "google_meet"
  | "zoom"
  | "microsoft_teams";

export type EventType = {
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
  buffer_before_minutes: number;
  buffer_after_minutes: number;
  minimum_notice_minutes: number;
  /** Booking window in days; null means unlimited. */
  max_days_in_advance: number | null;
  /** Max bookings of this event type per day; null means unlimited. */
  daily_booking_limit: number | null;
  location_type: LocationType;
  /** Address (in_person), phone number (phone) or meeting URL (custom_link); null otherwise. */
  location_value: string | null;
};

export type EventTypeInput = Omit<EventType, "id" | "slug">;

export const eventTypesApi = {
  list: () => apiRequest<EventType[]>("/event-types"),
  create: (input: EventTypeInput) =>
    apiRequest<EventType>("/event-types", {
      method: "POST",
      body: JSON.stringify(input),
    }),
  update: (id: string, input: EventTypeInput) =>
    apiRequest<EventType>(`/event-types/${id}`, {
      method: "PATCH",
      body: JSON.stringify(input),
    }),
  delete: (id: string) =>
    apiRequest<void>(`/event-types/${id}`, {
      method: "DELETE",
    }),
};
