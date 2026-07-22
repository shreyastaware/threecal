"use client";

import { DashboardHeader } from "@/features/dashboard/components/dashboard-header";
import { DashboardShell } from "@/features/dashboard/components/dashboard-shell";
import { BillingSettings } from "@/features/billing/components/billing-settings";
import { PaymentSettings } from "@/features/payments/components/payment-settings";

export function PaymentsPage() {
  return <DashboardShell><DashboardHeader eyebrow="Payments" title={<>Get paid<br/><em>without friction.</em></>} description="Connect the provider that should collect invitee payments, then verify your Threecal billing mandate." /><PaymentSettings /><BillingSettings /></DashboardShell>;
}
