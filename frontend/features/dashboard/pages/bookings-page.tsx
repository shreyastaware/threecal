"use client";

import { HostBookings } from "@/features/bookings/components/host-bookings";
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
      <HostBookings />
    </DashboardShell>
  );
}
