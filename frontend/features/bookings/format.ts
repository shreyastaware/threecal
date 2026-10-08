import type { BookingScope, BookingStatus, HostBooking } from "@/features/bookings/api";

/** Backend datetimes are UTC; tolerate values without an explicit offset. */
export function parseUtc(value: string) {
  return new Date(/(?:Z|[+-]\d{2}:?\d{2})$/.test(value) ? value : `${value}Z`);
}

export function dayKey(value: string, timezone: string) {
  const parts = new Intl.DateTimeFormat("en-CA", { timeZone: timezone, year: "numeric", month: "2-digit", day: "2-digit" }).formatToParts(parseUtc(value));
  const values = Object.fromEntries(parts.map((part) => [part.type, part.value]));
  return `${values.year}-${values.month}-${values.day}`;
}

export function formatDayLabel(value: string, timezone: string) {
  return new Intl.DateTimeFormat(undefined, { weekday: "long", month: "long", day: "numeric", year: "numeric", timeZone: timezone }).format(parseUtc(value));
}

export function formatTime(value: string, timezone: string) {
  return new Intl.DateTimeFormat(undefined, { hour: "numeric", minute: "2-digit", timeZone: timezone }).format(parseUtc(value));
}

export function formatTimeRange(startsAt: string, endsAt: string, timezone: string) {
  return `${formatTime(startsAt, timezone)} – ${formatTime(endsAt, timezone)}`;
}

/** e.g. "Wednesday, October 14, 2026 · 3:30 PM – 4:00 PM". */
export function formatWhen(startsAt: string, endsAt: string, timezone: string) {
  return `${formatDayLabel(startsAt, timezone)} · ${formatTimeRange(startsAt, endsAt, timezone)}`;
}

export function formatAmount(amountMinor: number, currency: string) {
  return new Intl.NumberFormat(undefined, { style: "currency", currency }).format(amountMinor / 100);
}

export type DisplayStatus = BookingStatus | "awaiting_payment" | "completed";

export function displayStatus(booking: Pick<HostBooking, "status" | "ends_at">, scope?: BookingScope): DisplayStatus {
  if (booking.status === "pending") return scope === "cancelled" ? "expired" : "awaiting_payment";
  if (booking.status === "confirmed" && parseUtc(booking.ends_at).getTime() <= Date.now()) return "completed";
  return booking.status;
}

export const statusLabels: Record<DisplayStatus, string> = {
  pending: "Pending",
  awaiting_payment: "Awaiting payment",
  confirmed: "Confirmed",
  completed: "Completed",
  cancelled: "Cancelled",
  expired: "Expired",
};

const refundLabels: Record<string, string> = {
  pending: "Refund pending",
  created: "Refund pending",
  processed: "Refunded",
  failed: "Refund failed",
};

/** Amount line for a booking, e.g. "₹500.00 · Refunded" or "Free". */
export function paymentSummary(booking: Pick<HostBooking, "booking_amount" | "currency" | "provider_payment_id" | "refund_status">) {
  if (!booking.booking_amount) return "Free";
  const amount = formatAmount(booking.booking_amount, booking.currency);
  if (booking.refund_status) return `${amount} · ${refundLabels[booking.refund_status] ?? "Refund pending"}`;
  return booking.provider_payment_id ? `${amount} · Paid` : `${amount} · Unpaid`;
}

export function isChangeable(booking: Pick<HostBooking, "status" | "starts_at">) {
  return (booking.status === "confirmed" || booking.status === "pending") && parseUtc(booking.starts_at).getTime() > Date.now();
}

/** e.g. "Tuesday, October 13, 2026 at 3:30 PM". */
export function formatDateTime(value: string, timezone: string) {
  return `${formatDayLabel(value, timezone)} at ${formatTime(value, timezone)}`;
}
