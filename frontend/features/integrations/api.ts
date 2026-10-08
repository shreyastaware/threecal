import { apiRequest } from "@/lib/api/client";

export type CalendarProvider = "google" | "microsoft";
export type ConferencingProvider = "zoom";
export type IntegrationProvider = CalendarProvider | ConferencingProvider;
export type ConnectionStatus = "active" | "reconnect_required";

export type CalendarConnection = {
  id: string;
  provider: CalendarProvider;
  account_email: string;
  status: ConnectionStatus;
  created_at: string;
  conflict_calendar_ids: string[];
  destination_calendar_id: string | null;
};

export type ProviderCalendar = {
  id: string;
  name: string;
  is_primary: boolean;
  can_write: boolean;
  check_conflicts: boolean;
  is_destination: boolean;
};

export type CalendarConnectionUpdate = {
  conflict_calendar_ids: string[];
  destination_calendar_id: string | null;
};

export type ConferencingConnection = {
  id: string;
  provider: ConferencingProvider;
  account_email: string;
  status: ConnectionStatus;
  created_at: string;
};

type AuthorizationUrl = { authorization_url: string };

export const integrationsApi = {
  listCalendarConnections: () => apiRequest<CalendarConnection[]>("/calendars/connections"),
  authorizeCalendar: (provider: CalendarProvider) =>
    apiRequest<AuthorizationUrl>(`/calendars/oauth/${provider}/authorize`),
  listCalendars: (connectionId: string) =>
    apiRequest<ProviderCalendar[]>(`/calendars/connections/${connectionId}/calendars`),
  updateCalendarConnection: (connectionId: string, input: CalendarConnectionUpdate) =>
    apiRequest<CalendarConnection>(`/calendars/connections/${connectionId}`, {
      method: "PATCH",
      body: JSON.stringify(input),
    }),
  deleteCalendarConnection: (connectionId: string) =>
    apiRequest<void>(`/calendars/connections/${connectionId}`, { method: "DELETE" }),
  listConferencingConnections: () => apiRequest<ConferencingConnection[]>("/conferencing/connections"),
  authorizeConferencing: (provider: ConferencingProvider) =>
    apiRequest<AuthorizationUrl>(`/conferencing/oauth/${provider}/authorize`),
  deleteConferencingConnection: (connectionId: string) =>
    apiRequest<void>(`/conferencing/connections/${connectionId}`, { method: "DELETE" }),
};
