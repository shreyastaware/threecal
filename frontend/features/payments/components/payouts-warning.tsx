"use client";

import { ArrowRight, CircleAlert } from "lucide-react";
import Link from "next/link";

import { usePaymentAccount } from "@/features/payments/hooks/use-payment-account";
import { activationStatusLabels } from "@/features/payments/schemas";

// Shown wherever a host has paid offers that invitees cannot book yet.
export function PayoutsWarning({ hasPaidEvents }: { hasPaidEvents: boolean }) {
  const account = usePaymentAccount();
  if (!hasPaidEvents || account.isLoading || account.isError || account.data?.payouts_enabled) {
    return null;
  }
  const detail = account.data
    ? `Payout status: ${activationStatusLabels[account.data.activation_status]}. Paid event types can't be booked until payouts are active.`
    : "Add your bank account so invitees can book and pay for your paid event types.";
  return (
    <section className="setup-banner">
      <CircleAlert size={19} />
      <div>
        <strong>Paid bookings are paused</strong>
        <p>{detail}</p>
      </div>
      <Link className="text-link" href="/dashboard/payments">
        {account.data ? "Review payouts" : "Set up payouts"} <ArrowRight size={14} />
      </Link>
    </section>
  );
}
