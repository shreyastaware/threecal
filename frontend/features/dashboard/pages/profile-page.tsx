"use client";

import { DashboardHeader } from "@/features/dashboard/components/dashboard-header";
import { DashboardShell } from "@/features/dashboard/components/dashboard-shell";
import { useAuth } from "@/features/auth/hooks/use-auth";
import { ProfileDetails } from "@/features/scheduling/components/profile-details";

export function ProfilePage() {
  const { user } = useAuth();
  return <DashboardShell><DashboardHeader eyebrow="Profile" title={<>A public desk<br/><em>worth finding.</em></>} description="Review your public details, then edit one field at a time without changing anything else." />{user && <ProfileDetails user={user} />}</DashboardShell>;
}
