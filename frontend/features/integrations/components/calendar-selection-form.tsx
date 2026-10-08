"use client";

import { zodResolver } from "@hookform/resolvers/zod";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Check, LoaderCircle } from "lucide-react";
import posthog from "posthog-js";
import { Controller, useForm } from "react-hook-form";

import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { StatusMessage } from "@/features/dashboard/components/status-message";
import { integrationsApi, type CalendarConnection, type ProviderCalendar } from "@/features/integrations/api";
import { CALENDAR_CONNECTIONS_KEY } from "@/features/integrations/hooks/use-integrations";
import { calendarSelectionSchema, type CalendarSelectionValues } from "@/features/integrations/schemas";
import { getErrorMessage } from "@/lib/api/client";

// Select items need a non-empty value; mapped to null when saving.
const NO_DESTINATION = "none";

function toFormValues(calendars: ProviderCalendar[]): CalendarSelectionValues {
  return {
    conflict_calendar_ids: calendars.filter((item) => item.check_conflicts).map((item) => item.id),
    destination_calendar_id: calendars.find((item) => item.is_destination)?.id ?? NO_DESTINATION,
  };
}

export function CalendarSelectionForm({ connection }: { connection: CalendarConnection }) {
  const calendarsKey = ["integrations", "calendars", connection.id, "list"] as const;
  const calendars = useQuery({
    queryKey: calendarsKey,
    queryFn: () => integrationsApi.listCalendars(connection.id),
  });

  if (calendars.isLoading) {
    return <p className="integration-loading"><LoaderCircle className="spin" size={16} /> Loading calendars</p>;
  }
  if (calendars.isError || !calendars.data) {
    return <StatusMessage>{getErrorMessage(calendars.error, "We couldn't load your calendars.")}</StatusMessage>;
  }
  return <SelectionForm connection={connection} calendars={calendars.data} />;
}

function SelectionForm({ connection, calendars }: { connection: CalendarConnection; calendars: ProviderCalendar[] }) {
  const queryClient = useQueryClient();
  const {
    control,
    handleSubmit,
    reset,
    formState: { errors, isDirty },
  } = useForm<CalendarSelectionValues>({
    resolver: zodResolver(calendarSelectionSchema),
    defaultValues: toFormValues(calendars),
  });
  const save = useMutation({
    mutationFn: (values: CalendarSelectionValues) =>
      integrationsApi.updateCalendarConnection(connection.id, {
        conflict_calendar_ids: values.conflict_calendar_ids,
        destination_calendar_id: values.destination_calendar_id === NO_DESTINATION ? null : values.destination_calendar_id,
      }),
    onSuccess: async (_, values) => {
      reset(values);
      posthog.capture("calendar_selection_saved", {
        provider: connection.provider,
        conflict_calendars: values.conflict_calendar_ids.length,
        has_destination: values.destination_calendar_id !== NO_DESTINATION,
      });
      // The destination is unique per host, so other connections may have changed too.
      await queryClient.invalidateQueries({ queryKey: CALENDAR_CONNECTIONS_KEY });
    },
  });
  const writable = calendars.filter((item) => item.can_write);

  return (
    <form className="integration-calendars" onSubmit={handleSubmit((values) => save.mutate(values))} noValidate>
      <fieldset>
        <legend>
          <strong>Check for conflicts</strong>
          <small>Busy times on these calendars are hidden from your booking pages.</small>
        </legend>
        <Controller
          control={control}
          name="conflict_calendar_ids"
          render={({ field }) => (
            <div className="integration-calendar-list">
              {calendars.map((calendar) => {
                const checked = field.value.includes(calendar.id);
                return (
                  <label className="checkbox-field" key={calendar.id}>
                    <input
                      type="checkbox"
                      checked={checked}
                      onBlur={field.onBlur}
                      onChange={() => field.onChange(checked ? field.value.filter((id) => id !== calendar.id) : [...field.value, calendar.id])}
                    />
                    <span>
                      {calendar.name}
                      {calendar.is_primary && <small> · Primary</small>}
                    </span>
                  </label>
                );
              })}
            </div>
          )}
        />
        {errors.conflict_calendar_ids && <small className="field-error">{errors.conflict_calendar_ids.message}</small>}
      </fieldset>
      <label className="integration-destination">
        <span>Add new bookings to</span>
        <Controller
          control={control}
          name="destination_calendar_id"
          render={({ field }) => (
            <Select inputRef={field.ref} name={field.name} onValueChange={(value) => field.onChange(value ?? NO_DESTINATION)} value={field.value}>
              <SelectTrigger aria-label="Destination calendar" className="dashboard-select-trigger" onBlur={field.onBlur}>
                <SelectValue>
                  {(value: string) => writable.find((item) => item.id === value)?.name ?? "Don't add bookings to this account"}
                </SelectValue>
              </SelectTrigger>
              <SelectContent className="dashboard-select-content">
                <SelectItem value={NO_DESTINATION}>Don&apos;t add bookings to this account</SelectItem>
                {writable.map((calendar) => (
                  <SelectItem key={calendar.id} value={calendar.id}>{calendar.name}</SelectItem>
                ))}
              </SelectContent>
            </Select>
          )}
        />
        <small className="field-hint">Only one calendar across your accounts receives new bookings.</small>
      </label>
      {save.isError && <StatusMessage>{getErrorMessage(save.error)}</StatusMessage>}
      {save.isSuccess && !isDirty && <StatusMessage tone="success">Calendar settings saved.</StatusMessage>}
      <button className="save-button" type="submit" disabled={save.isPending || !isDirty}>
        {save.isPending ? <LoaderCircle className="spin" size={16} /> : <Check size={16} />} {save.isPending ? "Saving" : "Save calendars"}
      </button>
    </form>
  );
}
