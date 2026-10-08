import { z } from "zod";

import type { IntegrationProvider } from "@/features/integrations/api";

export const providerLabels: Record<IntegrationProvider, string> = {
  google: "Google Calendar",
  microsoft: "Outlook Calendar",
  zoom: "Zoom",
};

export const calendarSelectionSchema = z.object({
  conflict_calendar_ids: z.array(z.string()).max(50, "Choose up to 50 calendars"),
  // Empty string means "don't add bookings to this account".
  destination_calendar_id: z.string(),
});

export type CalendarSelectionValues = z.infer<typeof calendarSelectionSchema>;

const errorMessages: Record<string, string> = {
  access_denied: "The connection was cancelled before access was granted.",
  invalid_state: "That connection link expired. Please try connecting again.",
  connection_failed: "We couldn't finish connecting. Please try again.",
  not_configured: "This integration isn't available yet.",
};

export function oauthErrorMessage(code: string): string {
  return errorMessages[code] ?? "We couldn't finish connecting. Please try again.";
}

export function connectedMessage(provider: string): string | null {
  return provider in providerLabels
    ? `${providerLabels[provider as IntegrationProvider]} is connected.`
    : null;
}
