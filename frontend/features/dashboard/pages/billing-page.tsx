"use client";

import { Check } from "lucide-react";
import { useSearchParams } from "next/navigation";

import { BillingSettings } from "@/features/billing/components/billing-settings";
import { DashboardHeader } from "@/features/dashboard/components/dashboard-header";
import { DashboardShell } from "@/features/dashboard/components/dashboard-shell";
import { StatusMessage } from "@/features/dashboard/components/status-message";

export function BillingPage() {
  const searchParams = useSearchParams();
  const returned = searchParams.get("setup") === "complete";
  return <DashboardShell><DashboardHeader eyebrow="Platform billing" title={<>Verify your<br/><em>billing mandate.</em></>} description="A recurring mandate keeps your monthly platform fee ready when paid bookings generate earnings." />{returned && <StatusMessage tone="success"><Check size={14}/> Checkout returned. Enter the payment method and subscription IDs below to finish verification.</StatusMessage>}<BillingSettings /></DashboardShell>;
}
