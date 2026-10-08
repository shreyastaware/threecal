import { describe, expect, it } from "vitest";

import { publicLocationLabel } from "@/features/event-types/locations";
import { eventTypeSchema, type EventTypeFormValues } from "@/features/event-types/schemas";

const base: EventTypeFormValues = {
  title: "Strategy call",
  description: "",
  duration_option: "30",
  custom_duration_minutes: undefined,
  slot_interval_minutes: 30,
  price: 0,
  is_active: true,
  is_default: false,
  buffer_before_minutes: 0,
  buffer_after_minutes: 0,
  minimum_notice_value: 0,
  minimum_notice_unit: "hours",
  max_days_in_advance: 60,
  daily_booking_limit: null,
  location_type: "none",
  location_value: "",
};

function locationError(values: Partial<EventTypeFormValues>) {
  const result = eventTypeSchema.safeParse({ ...base, ...values });
  return result.success ? null : result.error.issues.find((issue) => issue.path[0] === "location_value")?.message ?? null;
}

describe("event type location", () => {
  it("accepts integration locations without a value", () => {
    expect(locationError({ location_type: "google_meet" })).toBeNull();
    expect(locationError({ location_type: "zoom" })).toBeNull();
  });

  it("requires an address for in-person meetings", () => {
    expect(locationError({ location_type: "in_person" })).toBe("Enter the meeting address");
    expect(locationError({ location_type: "in_person", location_value: "12 Market Street" })).toBeNull();
  });

  it("validates phone numbers and meeting links", () => {
    expect(locationError({ location_type: "phone", location_value: "call me" })).toBe("Enter a valid phone number");
    expect(locationError({ location_type: "phone", location_value: "+91 98765 43210" })).toBeNull();
    expect(locationError({ location_type: "custom_link", location_value: "whereby.com/room" })).toMatch(/valid meeting link/);
    expect(locationError({ location_type: "custom_link", location_value: "https://whereby.com/room" })).toBeNull();
  });

  it("labels locations for invitees without exposing links", () => {
    expect(publicLocationLabel("in_person", "12 Market Street")).toBe("In person: 12 Market Street");
    expect(publicLocationLabel("custom_link", "https://secret.example")).toBe("Online meeting");
    expect(publicLocationLabel("google_meet", null)).toBe("Google Meet");
    expect(publicLocationLabel("none", null)).toBeNull();
  });
});
