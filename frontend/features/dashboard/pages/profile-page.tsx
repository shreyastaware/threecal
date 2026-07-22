"use client";

import { DashboardHeader } from "@/features/dashboard/components/dashboard-header";
import { DashboardShell } from "@/features/dashboard/components/dashboard-shell";
import { useAuth } from "@/features/auth/hooks/use-auth";
import { ProfileEditor } from "@/features/scheduling/components/profile-editor";

export function ProfilePage() {
  const { user } = useAuth();
  return <DashboardShell><DashboardHeader eyebrow="Profile" title={<>A public desk<br/><em>worth finding.</em></>} description="Your name, image, bio, timezone, and username appear on every booking page." />{user && <ProfileEditor user={user} />}</DashboardShell>;
}
