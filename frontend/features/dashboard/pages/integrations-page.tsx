"use client";

import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";

import { DashboardHeader } from "@/features/dashboard/components/dashboard-header";
import { DashboardShell } from "@/features/dashboard/components/dashboard-shell";
import { StatusMessage } from "@/features/dashboard/components/status-message";
import { IntegrationsManager } from "@/features/integrations/components/integrations-manager";
import { connectedMessage, oauthErrorMessage } from "@/features/integrations/schemas";

export function IntegrationsPage({ connected, error }: { connected: string | null; error: string | null }) {
  const router = useRouter();
  // Captured once so the message survives clearing the OAuth query params below.
  const [result] = useState(() => {
    if (error) return { tone: "error" as const, message: oauthErrorMessage(error) };
    const message = connected ? connectedMessage(connected) : null;
    return message ? { tone: "success" as const, message } : null;
  });

  useEffect(() => {
    if (connected || error) router.replace("/dashboard/integrations", { scroll: false });
  }, [connected, error, router]);

  return (
    <DashboardShell>
      <DashboardHeader
        eyebrow="Integrations"
        title={<>Connect your tools.<br/><em>Never double-book.</em></>}
        description="Sync your calendars to block busy times and add new bookings automatically, and create video links for every meeting."
      />
      {result && <StatusMessage tone={result.tone}>{result.message}</StatusMessage>}
      <IntegrationsManager />
    </DashboardShell>
  );
}
