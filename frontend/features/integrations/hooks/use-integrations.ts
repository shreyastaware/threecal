"use client";

import { useQuery } from "@tanstack/react-query";

import { useAuth } from "@/features/auth/hooks/use-auth";
import { integrationsApi } from "@/features/integrations/api";

export const CALENDAR_CONNECTIONS_KEY = ["integrations", "calendars"] as const;
export const CONFERENCING_CONNECTIONS_KEY = ["integrations", "conferencing"] as const;

export function useCalendarConnections() {
  const { user } = useAuth();
  return useQuery({
    queryKey: CALENDAR_CONNECTIONS_KEY,
    queryFn: integrationsApi.listCalendarConnections,
    enabled: Boolean(user),
  });
}

export function useConferencingConnections() {
  const { user } = useAuth();
  return useQuery({
    queryKey: CONFERENCING_CONNECTIONS_KEY,
    queryFn: integrationsApi.listConferencingConnections,
    enabled: Boolean(user),
  });
}
