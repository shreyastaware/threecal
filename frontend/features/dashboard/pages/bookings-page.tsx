"use client";

import { CalendarDays } from "lucide-react";

import { DashboardHeader } from "@/features/dashboard/components/dashboard-header";
import { DashboardShell } from "@/features/dashboard/components/dashboard-shell";

export function BookingsPage() {
  return <DashboardShell><DashboardHeader eyebrow="Bookings" title={<>A clear view of<br/><em>what is next.</em></>} description="Booking-list, status, and cancellation endpoints are not exposed by the current API yet." /><section className="empty-feature"><CalendarDays size={26}/><h2>Booking management is API-bound</h2><p>Public bookings are created and paid through their event link. Once the backend exposes a host booking list, this view is ready for that data without changing the workspace navigation.</p></section></DashboardShell>;
}
