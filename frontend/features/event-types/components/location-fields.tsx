"use client";

import Link from "next/link";
import { type Control, Controller, type FieldErrors, type UseFormRegister, useWatch } from "react-hook-form";

import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import type { LocationType } from "@/features/event-types/api";
import { LOCATION_LABELS } from "@/features/event-types/locations";
import { LOCATION_TYPES, type EventTypeFormValues } from "@/features/event-types/schemas";

const VALUE_FIELDS: Partial<Record<LocationType, { label: string; placeholder: string; inputMode?: "tel" | "url"; hint: string }>> = {
  in_person: { label: "Address", placeholder: "12 Market Street, Bengaluru", hint: "Shown on your booking page and in confirmations." },
  phone: { label: "Phone number", placeholder: "+91 98765 43210", inputMode: "tel", hint: "The number invitees should call, or that you will call from." },
  custom_link: { label: "Meeting link", placeholder: "https://whereby.com/your-room", inputMode: "url", hint: "Shared with invitees once their booking is confirmed." },
};

const INTEGRATION_HINTS: Partial<Record<LocationType, string>> = {
  google_meet: "A Google Meet link is created for each booking. Requires a connected Google Calendar.",
  zoom: "A Zoom meeting is created for each booking. Requires a connected Zoom account.",
  microsoft_teams: "A Teams meeting is created for each booking. Requires a connected Outlook work or school account.",
};

type LocationFieldsProps = {
  control: Control<EventTypeFormValues>;
  errors: FieldErrors<EventTypeFormValues>;
  register: UseFormRegister<EventTypeFormValues>;
};

export function LocationFields({ control, errors, register }: LocationFieldsProps) {
  const locationType = useWatch({ control, name: "location_type" });
  const valueField = VALUE_FIELDS[locationType];
  const integrationHint = INTEGRATION_HINTS[locationType];

  return (
    <fieldset className="booking-rules-fields location-fields">
      <legend>
        <strong>Location</strong>
        <small>Where the meeting happens. Online locations get a unique link for every booking.</small>
      </legend>
      <label>
        <span>Location type</span>
        <Controller
          control={control}
          name="location_type"
          render={({ field }) => (
            <Select inputRef={field.ref} name={field.name} onValueChange={field.onChange} value={field.value}>
              <SelectTrigger aria-label="Location type" className="dashboard-select-trigger" onBlur={field.onBlur}>
                <SelectValue>{(value: LocationType) => LOCATION_LABELS[value]}</SelectValue>
              </SelectTrigger>
              <SelectContent className="dashboard-select-content">
                {LOCATION_TYPES.map((value) => (
                  <SelectItem key={value} value={value}>{LOCATION_LABELS[value]}</SelectItem>
                ))}
              </SelectContent>
            </Select>
          )}
        />
        {integrationHint && (
          <small className="field-hint">
            {integrationHint} <Link className="text-link" href="/dashboard/integrations">Manage integrations</Link>
          </small>
        )}
      </label>
      {valueField && (
        <label>
          <span>{valueField.label}</span>
          <input
            inputMode={valueField.inputMode}
            placeholder={valueField.placeholder}
            type={valueField.inputMode === "url" ? "url" : "text"}
            {...register("location_value")}
          />
          <small className="field-hint">{valueField.hint}</small>
          {errors.location_value && <small className="field-error">{errors.location_value.message}</small>}
        </label>
      )}
    </fieldset>
  );
}
