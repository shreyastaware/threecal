"use client";

import { useQuery } from "@tanstack/react-query";
import { ArrowRight, CircleAlert, Link2, Route } from "lucide-react";
import Link from "next/link";

import { useAuth } from "@/features/auth/hooks/use-auth";
import { NextBookings } from "@/features/bookings/components/next-bookings";
import { DashboardHeader } from "@/features/dashboard/components/dashboard-header";
import { DashboardShell } from "@/features/dashboard/components/dashboard-shell";
import { StatusMessage } from "@/features/dashboard/components/status-message";
import { eventTypesApi } from "@/features/event-types/api";
import { PayoutsWarning } from "@/features/payments/components/payouts-warning";
import { usePaymentAccount } from "@/features/payments/hooks/use-payment-account";
import { activationStatusLabels } from "@/features/payments/schemas";
import { getErrorMessage } from "@/lib/api/client";

export function DashboardPage() {
  const { user } = useAuth();
  const events = useQuery({ queryKey: ["event-types"], queryFn: eventTypesApi.list, enabled: Boolean(user) });
  const defaultEvent = events.data?.find((event) => event.is_default && event.is_active);
  const activeEventCount = events.data?.filter((event) => event.is_active).length ?? 0;
  const hasPaidEvents = Boolean(events.data?.some((event) => event.is_active && event.price_minor > 0));
  const payments = usePaymentAccount();
  const paidBookingsEnabled = Boolean(payments.data?.payouts_enabled);

  return <DashboardShell>
    <DashboardHeader eyebrow="Creator workspace" title={<>Shape your<br/><em>bookable hours.</em></>} description="A single place to tune your public links, offers, and availability." />
    {!user?.username && <section className="setup-banner"><CircleAlert size={19}/><div><strong>Finish your public profile</strong><p>Choose a booking URL before sharing event links.</p></div><Link className="text-link" href="/dashboard/profile">Set it up <ArrowRight size={14}/></Link></section>}
    <PayoutsWarning hasPaidEvents={hasPaidEvents} />
    <section className="stats-grid">
      <article><span>Event types</span><strong>{events.isLoading ? "..." : events.data?.length ?? 0}</strong><small>{events.data?.filter((event) => event.is_active).length ?? 0} visible publicly</small></article>
      <article><span>Live booking links</span><strong>{events.isLoading ? "..." : activeEventCount}</strong><small>Ready to share with invitees</small></article>
      <article><span>Paid bookings</span><strong>{payments.isLoading ? "..." : paidBookingsEnabled ? "Enabled" : "Paused"}</strong><small>{payments.data ? activationStatusLabels[payments.data.activation_status] : "Add a payout bank account"}{" · "}<Link className="text-link" href="/dashboard/payments">Payments</Link></small></article>
      <article><span>Default route</span><strong>{events.isLoading ? "..." : defaultEvent ? "Ready" : "Open"}</strong><small>{defaultEvent?.title ?? "No default event selected"}</small></article>
    </section>
    {events.isError && <StatusMessage>{getErrorMessage(events.error)}</StatusMessage>}
    <NextBookings />
    <section className="workspace-panel dashboard-links-panel">
      <div className="panel-heading"><div><span>Public links</span><h2>Share your time</h2></div><p>Your main link opens the default booking, or your public page when no default is selected.</p></div>
      <div className="public-link-list">
        {user?.username && <div className="public-link-row public-link-primary"><Route size={16}/><span>threecal.com/{user.username}</span><small>{defaultEvent ? `Opens ${defaultEvent.title}` : "Shows all event types"}</small><Link className="text-link" href={`/${user.username}`} target="_blank">Open <ArrowRight size={14}/></Link></div>}
        {events.data?.filter((event) => event.is_active).map((event) => <div className="public-link-row" key={event.id}><Link2 size={16}/><span>{user?.username ? `threecal.com/${user.username}/${event.slug}` : "Choose a username first"}</span>{user?.username && <Link className="text-link" href={`/${user.username}/${event.slug}`} target="_blank">Open <ArrowRight size={14}/></Link>}</div>)}
        {!events.isLoading && !events.data?.length && <p>Create an event type to get your first public link.</p>}
      </div>
    </section>
  </DashboardShell>;
}
