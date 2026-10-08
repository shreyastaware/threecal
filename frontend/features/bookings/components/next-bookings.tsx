"use client";

import { useQuery } from "@tanstack/react-query";
import { ArrowRight, Video } from "lucide-react";
import Link from "next/link";

import { useAuth } from "@/features/auth/hooks/use-auth";
import { hostBookingsApi } from "@/features/bookings/api";
import { BookingStatusBadge } from "@/features/bookings/components/booking-status-badge";
import { HOST_BOOKINGS_KEY } from "@/features/bookings/components/host-bookings";
import { displayStatus, formatDayLabel, formatTimeRange } from "@/features/bookings/format";
import { StatusMessage } from "@/features/dashboard/components/status-message";
import { getErrorMessage } from "@/lib/api/client";

/** Compact list of the host's next few bookings for the dashboard home. */
export function NextBookings({ limit = 5 }: { limit?: number }) {
  const { user } = useAuth();
  const timezone = user?.timezone ?? "UTC";
  const bookings = useQuery({
    queryKey: [...HOST_BOOKINGS_KEY, "next", limit],
    queryFn: () => hostBookingsApi.list({ scope: "upcoming", limit }),
    enabled: Boolean(user),
  });

  return (
    <section className="workspace-panel next-bookings-panel">
      <div className="panel-heading">
        <div><span>Schedule</span><h2>Next bookings</h2></div>
        <p>Your upcoming appointments, in {timezone}. <Link className="text-link" href="/dashboard/bookings">All bookings <ArrowRight size={14}/></Link></p>
      </div>
      <div className="public-link-list">
        {bookings.isLoading && <p>Loading bookings...</p>}
        {bookings.isError && <StatusMessage>{getErrorMessage(bookings.error)}</StatusMessage>}
        {bookings.data?.items.map((booking) => (
          <div className="public-link-row next-booking-row" key={booking.id}>
            <span>
              <strong>{booking.invitee_name}</strong> · {booking.event_type_title}
            </span>
            <small>{formatDayLabel(booking.starts_at, timezone)} · {formatTimeRange(booking.starts_at, booking.ends_at, timezone)}</small>
            <BookingStatusBadge status={displayStatus(booking, "upcoming")} />
            {booking.meeting_url && booking.status === "confirmed" && (
              <a className="text-link" href={booking.meeting_url} target="_blank" rel="noreferrer"><Video size={14}/> Join</a>
            )}
          </div>
        ))}
        {bookings.data && !bookings.data.items.length && <p>No upcoming bookings yet. Share your booking link to fill your calendar.</p>}
      </div>
    </section>
  );
}
