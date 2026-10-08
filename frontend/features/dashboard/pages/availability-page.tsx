"use client";

import { DashboardHeader } from "@/features/dashboard/components/dashboard-header";
import { DashboardShell } from "@/features/dashboard/components/dashboard-shell";
import { DateOverrides } from "@/features/scheduling/components/date-overrides";
import { ScheduleEditor } from "@/features/scheduling/components/schedule-editor";

export function AvailabilityPage() {
  return <DashboardShell><DashboardHeader eyebrow="03 / Availability" title={<>Find your<br/><em>working rhythm.</em></>} description="Set weekly hours and breaks in your profile timezone. Saving replaces the complete schedule. Date overrides adjust single days." /><ScheduleEditor /><DateOverrides /></DashboardShell>;
}
