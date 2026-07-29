"use client";

import { DashboardHeader } from "@/features/dashboard/components/dashboard-header";
import { DashboardShell } from "@/features/dashboard/components/dashboard-shell";
import { PaymentAccountManager } from "@/features/payments/components/payment-account-manager";

export function PaymentsPage() {
  return (
    <DashboardShell>
      <DashboardHeader
        eyebrow="Payment settings"
        title={<>Get paid.<br/><em>Stay in control.</em></>}
        description="Connect your settlement account, complete your KYC details, and keep a clear record of where booking payments land."
      />
      <PaymentAccountManager />
    </DashboardShell>
  );
}
