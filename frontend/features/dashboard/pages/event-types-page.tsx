"use client";

import { useQuery } from "@tanstack/react-query";

import { DashboardHeader } from "@/features/dashboard/components/dashboard-header";
import { DashboardShell } from "@/features/dashboard/components/dashboard-shell";
import { eventTypesApi } from "@/features/event-types/api";
import { EventTypeManager } from "@/features/event-types/components/event-type-manager";
import { PayoutsWarning } from "@/features/payments/components/payouts-warning";

export function EventTypesPage() {
  // Shares the event type manager's query cache.
  const events = useQuery({ queryKey: ["event-types"], queryFn: eventTypesApi.list });
  const hasPaidEvents = Boolean(events.data?.some((event) => event.is_active && event.price_minor > 0));
  return <DashboardShell><DashboardHeader eyebrow="Your catalog" title={<>Make every<br/><em>session count.</em></>} description="Create free or paid offers with their own cadence and public booking link." /><PayoutsWarning hasPaidEvents={hasPaidEvents} /><EventTypeManager /></DashboardShell>;
}
