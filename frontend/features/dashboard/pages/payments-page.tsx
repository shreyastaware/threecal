"use client";

import { DashboardHeader } from "@/features/dashboard/components/dashboard-header";
import { DashboardShell } from "@/features/dashboard/components/dashboard-shell";
import { BillingSettings } from "@/features/billing/components/billing-settings";
import { PaymentSettings } from "@/features/payments/components/payment-settings";

export function PaymentsPage() {
  return <DashboardShell><DashboardHeader eyebrow="Payments" title={<>Get paid<br/><em>without friction.</em></>} description="Connect your own payment account securely with OAuth. Provider credentials stay off this dashboard." /><PaymentSettings /><BillingSettings /></DashboardShell>;
}
