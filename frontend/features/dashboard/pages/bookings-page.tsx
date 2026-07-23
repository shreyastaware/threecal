"use client";

import { CalendarDays } from "lucide-react";

import { DashboardHeader } from "@/features/dashboard/components/dashboard-header";
import { DashboardShell } from "@/features/dashboard/components/dashboard-shell";

export function BookingsPage() {
  return (
    <DashboardShell>
      <DashboardHeader
        eyebrow="Bookings"
        title={
          <>
            Your schedule,
            <br />
            <em>all in one place.</em>
          </>
        }
        description="See who has booked time with you and keep track of every upcoming appointment."
      />
      <section className="empty-feature">
        <CalendarDays aria-hidden="true" size={26} />
        <h2>No bookings yet</h2>
        <p>
          When someone books time with you, their appointment will appear here.
          Share your booking link to get your first booking.
        </p>
      </section>
    </DashboardShell>
  );
}
