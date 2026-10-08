"use client";

import { useMutation, useQueryClient } from "@tanstack/react-query";
import {
  CalendarDays,
  CalendarRange,
  ChevronDown,
  CircleAlert,
  CircleCheck,
  LoaderCircle,
  Plus,
  RefreshCw,
  Unplug,
  Video,
} from "lucide-react";
import posthog from "posthog-js";
import { useState } from "react";

import { StatusMessage } from "@/features/dashboard/components/status-message";
import {
  integrationsApi,
  type CalendarConnection,
  type CalendarProvider,
  type ConferencingConnection,
  type ConferencingProvider,
  type IntegrationProvider,
} from "@/features/integrations/api";
import { CalendarSelectionForm } from "@/features/integrations/components/calendar-selection-form";
import {
  CALENDAR_CONNECTIONS_KEY,
  CONFERENCING_CONNECTIONS_KEY,
  useCalendarConnections,
  useConferencingConnections,
} from "@/features/integrations/hooks/use-integrations";
import { providerLabels } from "@/features/integrations/schemas";
import { getErrorMessage } from "@/lib/api/client";

const calendarProviders: { provider: CalendarProvider; description: string; icon: typeof CalendarDays }[] = [
  { provider: "google", description: "Block busy times, add bookings to your calendar and create Google Meet links.", icon: CalendarDays },
  { provider: "microsoft", description: "Block busy times from Outlook and add bookings to your Outlook calendar.", icon: CalendarRange },
];

function useConnect() {
  return useMutation({
    mutationFn: async (provider: IntegrationProvider) => {
      const { authorization_url: url } = provider === "zoom"
        ? await integrationsApi.authorizeConferencing(provider)
        : await integrationsApi.authorizeCalendar(provider);
      posthog.capture("integration_connect_started", { provider });
      window.location.assign(url);
    },
  });
}

function ConnectionStatusBadge({ status }: { status: CalendarConnection["status"] }) {
  return status === "active"
    ? <span className="settings-badge verified"><CircleCheck size={12} /> Connected</span>
    : <span className="settings-badge pending"><CircleAlert size={12} /> Reconnect needed</span>;
}

function CalendarConnectionRow({ connection, onReconnect, reconnecting }: { connection: CalendarConnection; onReconnect: () => void; reconnecting: boolean }) {
  const queryClient = useQueryClient();
  const [expanded, setExpanded] = useState(false);
  const disconnect = useMutation({
    mutationFn: () => integrationsApi.deleteCalendarConnection(connection.id),
    onSuccess: async () => {
      posthog.capture("integration_disconnected", { provider: connection.provider });
      await queryClient.invalidateQueries({ queryKey: CALENDAR_CONNECTIONS_KEY });
    },
  });
  const needsReconnect = connection.status === "reconnect_required";

  return (
    <li className="integration-connection">
      <div className="integration-connection-row">
        <div>
          <strong>{connection.account_email}</strong>
          <small>
            {connection.conflict_calendar_ids.length} calendar{connection.conflict_calendar_ids.length === 1 ? "" : "s"} checked for conflicts
            {connection.destination_calendar_id ? " · receives new bookings" : ""}
          </small>
        </div>
        <ConnectionStatusBadge status={connection.status} />
      </div>
      {needsReconnect && (
        <StatusMessage tone="notice">Access to this calendar expired or was revoked. Reconnect it to keep checking conflicts.</StatusMessage>
      )}
      <div className="integration-actions">
        {needsReconnect ? (
          <button className="payment-connect-button" type="button" disabled={reconnecting} onClick={onReconnect}>
            {reconnecting ? <LoaderCircle className="spin" size={14} /> : <RefreshCw size={14} />} Reconnect
          </button>
        ) : (
          <button className="quiet-button" type="button" aria-expanded={expanded} onClick={() => setExpanded((open) => !open)}>
            <ChevronDown size={14} className={expanded ? "integration-chevron open" : "integration-chevron"} /> Choose calendars
          </button>
        )}
        <button className="quiet-button" type="button" disabled={disconnect.isPending} onClick={() => disconnect.mutate()}>
          {disconnect.isPending ? <LoaderCircle className="spin" size={14} /> : <Unplug size={14} />} Disconnect
        </button>
      </div>
      {disconnect.isError && <StatusMessage>{getErrorMessage(disconnect.error)}</StatusMessage>}
      {expanded && !needsReconnect && <CalendarSelectionForm connection={connection} />}
    </li>
  );
}

function CalendarProviderCard({ provider, description, icon: Icon, connections }: {
  provider: CalendarProvider;
  description: string;
  icon: typeof CalendarDays;
  connections: CalendarConnection[];
}) {
  const connect = useConnect();
  return (
    <article className="integration-card">
      <header>
        <span className="integration-mark"><Icon size={20} /></span>
        <div>
          <h3>{providerLabels[provider]}</h3>
          <p>{description}</p>
        </div>
      </header>
      {connections.length > 0 && (
        <ul className="integration-connections">
          {connections.map((connection) => (
            <CalendarConnectionRow
              connection={connection}
              key={connection.id}
              onReconnect={() => connect.mutate(provider)}
              reconnecting={connect.isPending}
            />
          ))}
        </ul>
      )}
      {connect.isError && <StatusMessage>{getErrorMessage(connect.error)}</StatusMessage>}
      <button
        className={connections.length ? "quiet-button" : "payment-connect-button"}
        type="button"
        disabled={connect.isPending}
        onClick={() => connect.mutate(provider)}
      >
        {connect.isPending ? <LoaderCircle className="spin" size={14} /> : <Plus size={14} />}
        {connections.length ? "Connect another account" : `Connect ${providerLabels[provider]}`}
      </button>
    </article>
  );
}

function ZoomCard({ connection }: { connection: ConferencingConnection | undefined }) {
  const queryClient = useQueryClient();
  const connect = useConnect();
  const provider: ConferencingProvider = "zoom";
  const disconnect = useMutation({
    mutationFn: (id: string) => integrationsApi.deleteConferencingConnection(id),
    onSuccess: async () => {
      posthog.capture("integration_disconnected", { provider });
      await queryClient.invalidateQueries({ queryKey: CONFERENCING_CONNECTIONS_KEY });
    },
  });
  return (
    <article className="integration-card">
      <header>
        <span className="integration-mark"><Video size={20} /></span>
        <div>
          <h3>{providerLabels.zoom}</h3>
          <p>Create a unique Zoom meeting for every booking. Choose Zoom as the location on an event type.</p>
        </div>
      </header>
      {connection && (
        <ul className="integration-connections">
          <li className="integration-connection">
            <div className="integration-connection-row">
              <div><strong>{connection.account_email}</strong><small>Meetings are created on this Zoom account.</small></div>
              <ConnectionStatusBadge status={connection.status} />
            </div>
            {connection.status === "reconnect_required" && (
              <StatusMessage tone="notice">Zoom access expired or was revoked. Reconnect to keep creating meeting links.</StatusMessage>
            )}
            <div className="integration-actions">
              {connection.status === "reconnect_required" && (
                <button className="payment-connect-button" type="button" disabled={connect.isPending} onClick={() => connect.mutate(provider)}>
                  <RefreshCw size={14} /> Reconnect
                </button>
              )}
              <button className="quiet-button" type="button" disabled={disconnect.isPending} onClick={() => disconnect.mutate(connection.id)}>
                {disconnect.isPending ? <LoaderCircle className="spin" size={14} /> : <Unplug size={14} />} Disconnect
              </button>
            </div>
          </li>
        </ul>
      )}
      {(connect.isError || disconnect.isError) && <StatusMessage>{getErrorMessage(connect.error ?? disconnect.error)}</StatusMessage>}
      {!connection && (
        <button className="payment-connect-button" type="button" disabled={connect.isPending} onClick={() => connect.mutate(provider)}>
          {connect.isPending ? <LoaderCircle className="spin" size={14} /> : <Plus size={14} />} Connect Zoom
        </button>
      )}
    </article>
  );
}

export function IntegrationsManager() {
  const calendars = useCalendarConnections();
  const conferencing = useConferencingConnections();

  return (
    <div className="integrations-manager">
      <section className="workspace-panel">
        <div className="panel-heading">
          <div><span>01 / Calendars</span><h2>Calendars</h2></div>
          <p>Connected calendars keep you from being double-booked, and new bookings are added to the calendar you choose.</p>
        </div>
        <div className="integration-stack">
          {calendars.isLoading && <p className="integration-loading"><LoaderCircle className="spin" size={16} /> Loading connections</p>}
          {calendars.isError && <StatusMessage>{getErrorMessage(calendars.error)}</StatusMessage>}
          {calendars.data && calendarProviders.map((item) => (
            <CalendarProviderCard
              key={item.provider}
              {...item}
              connections={calendars.data.filter((connection) => connection.provider === item.provider)}
            />
          ))}
        </div>
      </section>
      <section className="workspace-panel">
        <div className="panel-heading">
          <div><span>02 / Conferencing</span><h2>Video calls</h2></div>
          <p>Google Meet uses your Google Calendar connection and Microsoft Teams your Outlook work account. Zoom connects separately.</p>
        </div>
        <div className="integration-stack">
          {conferencing.isLoading && <p className="integration-loading"><LoaderCircle className="spin" size={16} /> Loading connections</p>}
          {conferencing.isError && <StatusMessage>{getErrorMessage(conferencing.error)}</StatusMessage>}
          {conferencing.data && <ZoomCard connection={conferencing.data.find((item) => item.provider === "zoom")} />}
        </div>
      </section>
    </div>
  );
}
