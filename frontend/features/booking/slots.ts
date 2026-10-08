import type { Slot } from "@/features/booking/api";

/** Days shown per page of the slot calendar (the slots API allows up to 31). */
export const SLOT_WINDOW_DAYS = 14;
/** How far ahead the calendar can page when an event type has no booking window. */
export const UNLIMITED_BOOKING_WINDOW_DAYS = 365;

/** YYYY-MM-DD for `date` as seen in `timezone`. */
export function dateStringInTimezone(date: Date, timezone: string) {
  const parts = new Intl.DateTimeFormat("en-CA", { timeZone: timezone, year: "numeric", month: "2-digit", day: "2-digit" }).formatToParts(date);
  const values = Object.fromEntries(parts.map((part) => [part.type, part.value]));
  return `${values.year}-${values.month}-${values.day}`;
}

/** Adds whole days to a YYYY-MM-DD string. */
export function addDays(day: string, days: number) {
  const value = new Date(`${day}T12:00:00Z`);
  value.setUTCDate(value.getUTCDate() + days);
  return dateStringInTimezone(value, "UTC");
}

export function groupSlots(slots: Slot[], timezone: string) {
  return slots.reduce<Record<string, Slot[]>>((groups, slot) => {
    const day = dateStringInTimezone(new Date(slot.starts_at), timezone);
    groups[day] = [...(groups[day] ?? []), slot];
    return groups;
  }, {});
}

export type SlotWindow = {
  start: string;
  end: string;
  hasPrevious: boolean;
  hasNext: boolean;
};

/**
 * The host-local date range for page `index` of the slot calendar, clipped to the
 * event type's booking window (`maxDaysInAdvance` days after today; null = unlimited).
 */
export function slotWindow(today: string, index: number, maxDaysInAdvance: number | null | undefined, windowDays = SLOT_WINDOW_DAYS): SlotWindow {
  const lastDay = addDays(today, maxDaysInAdvance ?? UNLIMITED_BOOKING_WINDOW_DAYS);
  const pages = Math.max(1, Math.ceil(((maxDaysInAdvance ?? UNLIMITED_BOOKING_WINDOW_DAYS) + 1) / windowDays));
  const page = Math.min(Math.max(index, 0), pages - 1);
  const start = addDays(today, page * windowDays);
  const naturalEnd = addDays(start, windowDays - 1);
  return {
    start,
    end: naturalEnd < lastDay ? naturalEnd : lastDay,
    hasPrevious: page > 0,
    hasNext: page < pages - 1,
  };
}

export function formatDayHeading(day: string) {
  return new Date(`${day}T12:00:00`).toLocaleDateString(undefined, { weekday: "short", month: "short", day: "numeric" });
}

export function formatSlotTime(value: string, timezone: string) {
  return new Date(value).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit", timeZone: timezone });
}
