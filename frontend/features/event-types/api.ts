import { apiRequest } from "@/lib/api/client";

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
};
