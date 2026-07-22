"use client";

import { useQuery } from "@tanstack/react-query";
import { ArrowRight, Check, CircleAlert, Link2 } from "lucide-react";
import Link from "next/link";
import { useSearchParams } from "next/navigation";

import { billingApi } from "@/features/billing/api";
import { BillingSettings } from "@/features/billing/components/billing-settings";
import { useAuth } from "@/features/auth/hooks/use-auth";
import { DashboardHeader } from "@/features/dashboard/components/dashboard-header";
import { DashboardShell } from "@/features/dashboard/components/dashboard-shell";
import { StatusMessage } from "@/features/dashboard/components/status-message";
import { eventTypesApi } from "@/features/event-types/api";
import { getErrorMessage } from "@/lib/api/client";

function formatInr(minor: number) {
  return new Intl.NumberFormat("en-IN", { style: "currency", currency: "INR" }).format(minor / 100);
}

export function DashboardPage() {
  const { user } = useAuth();
  const searchParams = useSearchParams();
  const events = useQuery({ queryKey: ["event-types"], queryFn: eventTypesApi.list, enabled: Boolean(user) });
  const billing = useQuery({ queryKey: ["billing"], queryFn: billingApi.get, enabled: Boolean(user) });
  const connected = searchParams.get("payment_provider") === "connected";

  return <DashboardShell>
    <DashboardHeader eyebrow="Creator workspace" title={<>Shape your<br/><em>bookable hours.</em></>} description="A single place to tune your public links, availability, and payment readiness." />
    {connected && <StatusMessage tone="success"><Check size={14}/> Payment provider connected successfully.</StatusMessage>}
    {!user?.username && <section className="setup-banner"><CircleAlert size={19}/><div><strong>Finish your public profile</strong><p>Choose a booking URL before sharing event links.</p></div><Link className="text-link" href="/dashboard/profile">Set it up <ArrowRight size={14}/></Link></section>}
    <section className="stats-grid">
      <article><span>Current cycle earnings</span><strong>{billing.isLoading ? "..." : formatInr(billing.data?.current_cycle_earnings ?? 0)}</strong><small>Confirmed paid bookings</small></article>
      <article><span>Event types</span><strong>{events.isLoading ? "..." : events.data?.length ?? 0}</strong><small>{events.data?.filter((event) => event.is_active).length ?? 0} visible publicly</small></article>
      <article><span>Payment readiness</span><strong>{billing.data?.ready ? "Ready" : "Setup"}</strong><small>{billing.data?.ready ? "Platform mandate verified" : "Required for paid events"}</small></article>
    </section>
    {billing.isError && <StatusMessage>{getErrorMessage(billing.error)}</StatusMessage>}
    <section className="workspace-panel dashboard-links-panel">
      <div className="panel-heading"><div><span>Public links</span><h2>Share your time</h2></div><p>Event-specific links are generated from your username and slug.</p></div>
      <div className="public-link-list">
        {events.data?.filter((event) => event.is_active).map((event) => <div className="public-link-row" key={event.id}><Link2 size={16}/><span>{user?.username ? `threecal.com/${user.username}/${event.slug}` : "Choose a username first"}</span>{user?.username && <Link className="text-link" href={`/${user.username}/${event.slug}`} target="_blank">Open <ArrowRight size={14}/></Link>}</div>)}
        {!events.isLoading && !events.data?.length && <p>Create an event type to get your first public link.</p>}
      </div>
    </section>
    <BillingSettings />
  </DashboardShell>;
}
