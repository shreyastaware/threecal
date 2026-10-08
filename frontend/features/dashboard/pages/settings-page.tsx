"use client";

import { ChangePasswordPanel } from "@/features/auth/components/change-password-panel";
import { DeleteAccountPanel } from "@/features/auth/components/delete-account-panel";
import { EmailVerificationPanel } from "@/features/auth/components/email-verification-panel";
import { useAuth } from "@/features/auth/hooks/use-auth";
import { DashboardHeader } from "@/features/dashboard/components/dashboard-header";
import { DashboardShell } from "@/features/dashboard/components/dashboard-shell";

export function SettingsPage() {
  const { user } = useAuth();
  return (
    <DashboardShell>
      <DashboardHeader
        eyebrow="Account settings"
        title={<>Keep the keys<br/><em>in your hands.</em></>}
        description="Manage your sign-in email, change your password, or close your account."
      />
      {user && <EmailVerificationPanel user={user} />}
      <ChangePasswordPanel />
      <DeleteAccountPanel />
    </DashboardShell>
  );
}
