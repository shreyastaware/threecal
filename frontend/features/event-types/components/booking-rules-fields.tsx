"use client";

import { type Control, Controller, type FieldErrors, type UseFormRegister } from "react-hook-form";

import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { NOTICE_UNIT_MINUTES, type EventTypeFormValues } from "@/features/event-types/schemas";

const NOTICE_UNITS = ["days", "hours", "minutes"] as const;

/** Express stored minutes in the largest unit that divides them evenly. */
export function noticeToFormValues(minutes: number): Pick<EventTypeFormValues, "minimum_notice_value" | "minimum_notice_unit"> {
  if (minutes === 0) return { minimum_notice_value: 0, minimum_notice_unit: "hours" };
  const unit = NOTICE_UNITS.find((item) => minutes % NOTICE_UNIT_MINUTES[item] === 0) ?? "minutes";
  return { minimum_notice_value: minutes / NOTICE_UNIT_MINUTES[unit], minimum_notice_unit: unit };
}

// Empty inputs mean "no limit" for the nullable rules.
const optionalNumber = (value: unknown) => (value === "" || value === null || value === undefined ? null : Number(value));

type BookingRulesFieldsProps = {
  control: Control<EventTypeFormValues>;
  errors: FieldErrors<EventTypeFormValues>;
  register: UseFormRegister<EventTypeFormValues>;
};

export function BookingRulesFields({ control, errors, register }: BookingRulesFieldsProps) {
  return (
    <fieldset className="booking-rules-fields">
      <legend>
        <strong>Booking rules</strong>
        <small>Control spacing between appointments and how far ahead people can book.</small>
      </legend>
      <label>
        <span>Buffer before (minutes)</span>
        <input type="number" inputMode="numeric" min="0" max="240" step="5" {...register("buffer_before_minutes", { valueAsNumber: true })} />
        {errors.buffer_before_minutes && <small className="field-error">{errors.buffer_before_minutes.message}</small>}
      </label>
      <label>
        <span>Buffer after (minutes)</span>
        <input type="number" inputMode="numeric" min="0" max="240" step="5" {...register("buffer_after_minutes", { valueAsNumber: true })} />
        {errors.buffer_after_minutes && <small className="field-error">{errors.buffer_after_minutes.message}</small>}
      </label>
      <label>
        <span>Minimum notice</span>
        <span className="booking-rules-notice">
          <input aria-label="Minimum notice amount" type="number" inputMode="numeric" min="0" step="1" {...register("minimum_notice_value", { valueAsNumber: true })} />
          <Controller
            control={control}
            name="minimum_notice_unit"
            render={({ field }) => (
              <Select inputRef={field.ref} name={field.name} onValueChange={field.onChange} value={field.value}>
                <SelectTrigger aria-label="Minimum notice unit" className="dashboard-select-trigger" onBlur={field.onBlur}>
                  <SelectValue />
                </SelectTrigger>
                <SelectContent className="dashboard-select-content">
                  <SelectItem value="minutes">Minutes</SelectItem>
                  <SelectItem value="hours">Hours</SelectItem>
                  <SelectItem value="days">Days</SelectItem>
                </SelectContent>
              </Select>
            )}
          />
        </span>
        <small className="field-hint">People cannot book a slot that starts sooner than this.</small>
        {errors.minimum_notice_value && <small className="field-error">{errors.minimum_notice_value.message}</small>}
      </label>
      <label>
        <span>Booking window (days)</span>
        <input type="number" inputMode="numeric" min="1" max="730" step="1" placeholder="Unlimited" {...register("max_days_in_advance", { setValueAs: optionalNumber })} />
        <small className="field-hint">How many days ahead people can book. Leave empty for no limit.</small>
        {errors.max_days_in_advance && <small className="field-error">{errors.max_days_in_advance.message}</small>}
      </label>
      <label>
        <span>Daily limit</span>
        <input type="number" inputMode="numeric" min="1" max="100" step="1" placeholder="Unlimited" {...register("daily_booking_limit", { setValueAs: optionalNumber })} />
        <small className="field-hint">Max bookings of this event per day. Leave empty for no limit.</small>
        {errors.daily_booking_limit && <small className="field-error">{errors.daily_booking_limit.message}</small>}
      </label>
    </fieldset>
  );
}
