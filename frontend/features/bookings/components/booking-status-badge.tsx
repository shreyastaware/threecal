import { statusLabels, type DisplayStatus } from "@/features/bookings/format";

export function BookingStatusBadge({ status }: { status: DisplayStatus }) {
  return <span className={`booking-status booking-status-${status}`}>{statusLabels[status]}</span>;
}
