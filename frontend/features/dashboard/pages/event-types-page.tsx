"use client";

import { DashboardHeader } from "@/features/dashboard/components/dashboard-header";
import { DashboardShell } from "@/features/dashboard/components/dashboard-shell";
import { EventTypeManager } from "@/features/event-types/components/event-type-manager";

export function EventTypesPage() {
  return <DashboardShell><DashboardHeader eyebrow="Your catalog" title={<>Make every<br/><em>session count.</em></>} description="Create free or paid offers with their own cadence and public booking link." /><EventTypeManager /></DashboardShell>;
}
