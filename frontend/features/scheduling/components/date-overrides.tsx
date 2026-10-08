"use client";

import { zodResolver } from "@hookform/resolvers/zod";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { CalendarOff, CalendarPlus, LoaderCircle, Trash2 } from "lucide-react";
import posthog from "posthog-js";
import { Controller, useForm, useWatch } from "react-hook-form";

import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { useAuth } from "@/features/auth/hooks/use-auth";
import { StatusMessage } from "@/features/dashboard/components/status-message";
import { schedulingApi, type DateOverride } from "@/features/scheduling/api";
import { dateOverrideSchema, type DateOverrideFormValues } from "@/features/scheduling/schemas";
import { getErrorMessage } from "@/lib/api/client";

export const OVERRIDES_QUERY_KEY = ["availability-overrides"] as const;

const emptyValues: DateOverrideFormValues = {
  date: "",
  mode: "unavailable",
  start_time: "09:00",
  end_time: "17:00",
  note: "",
};

// Today's date (YYYY-MM-DD) in the host's profile timezone, matching how the API validates overrides.
function todayIn(timeZone: string | undefined) {
  try {
    return new Intl.DateTimeFormat("en-CA", { timeZone, year: "numeric", month: "2-digit", day: "2-digit" }).format(new Date());
  } catch {
    return new Intl.DateTimeFormat("en-CA", { year: "numeric", month: "2-digit", day: "2-digit" }).format(new Date());
  }
}

function formatDate(value: string) {
  const [year, month, day] = value.split("-").map(Number);
  return new Date(year, month - 1, day).toLocaleDateString(undefined, { weekday: "short", day: "numeric", month: "short", year: "numeric" });
}

function timeValue(value: string | null) {
  return value ? value.slice(0, 5) : "";
}

export function DateOverrides() {
  const { user } = useAuth();
  const queryClient = useQueryClient();
  const today = todayIn(user?.timezone);
  const overrides = useQuery({
    queryKey: [...OVERRIDES_QUERY_KEY, today],
    queryFn: () => schedulingApi.listOverrides({ start: today }),
  });
  const {
    register,
    reset,
    handleSubmit,
    control,
    formState: { errors },
  } = useForm<DateOverrideFormValues>({ resolver: zodResolver(dateOverrideSchema), defaultValues: emptyValues });
  const mode = useWatch({ control, name: "mode" });

  const save = useMutation({
    mutationFn: (values: DateOverrideFormValues) =>
      schedulingApi.setOverride(values.date, {
        is_available: values.mode === "custom",
        start_time: values.mode === "custom" ? values.start_time : null,
        end_time: values.mode === "custom" ? values.end_time : null,
        note: values.note || null,
      }),
    onSuccess: (override) => {
      posthog.capture("availability_override_saved", { is_available: override.is_available });
      reset(emptyValues);
    },
    onSettled: () => queryClient.invalidateQueries({ queryKey: OVERRIDES_QUERY_KEY }),
  });
  const remove = useMutation({
    mutationFn: schedulingApi.deleteOverride,
    onSuccess: () => posthog.capture("availability_override_removed"),
    onSettled: () => queryClient.invalidateQueries({ queryKey: OVERRIDES_QUERY_KEY }),
  });

  const onSubmit = handleSubmit((values) => {
    remove.reset();
    save.mutate(values);
  });

  return (
    <section className="workspace-panel">
      <div className="panel-heading"><div><span>03 / Date overrides</span><h2>Exceptions to the rhythm</h2></div><p>Block out a full day or set different hours for one date. Custom hours replace that day&apos;s weekly hours and breaks.</p></div>
      <div className="override-body">
        <form className="event-form override-form" onSubmit={onSubmit} noValidate>
          <label>
            <span>Date</span>
            <input type="date" min={today} {...register("date")} />
            {errors.date && <small className="field-error">{errors.date.message}</small>}
          </label>
          <label>
            <span>Availability</span>
            <Controller
              control={control}
              name="mode"
              render={({ field }) => (
                <Select inputRef={field.ref} name={field.name} onValueChange={field.onChange} value={field.value}>
                  <SelectTrigger aria-label="Availability" className="dashboard-select-trigger" onBlur={field.onBlur}>
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent className="dashboard-select-content">
                    <SelectItem value="unavailable">Unavailable all day</SelectItem>
                    <SelectItem value="custom">Custom hours</SelectItem>
                  </SelectContent>
                </Select>
              )}
            />
          </label>
          {mode === "custom" && <>
            <label><span>From</span><input type="time" {...register("start_time")} />{errors.start_time && <small className="field-error">{errors.start_time.message}</small>}</label>
            <label><span>To</span><input type="time" {...register("end_time")} />{errors.end_time && <small className="field-error">{errors.end_time.message}</small>}</label>
          </>}
          <label className="event-description"><span>Note (optional)</span><input placeholder="Conference, holiday, late start…" {...register("note")} />{errors.note && <small className="field-error">{errors.note.message}</small>}<small className="field-hint">Saving a date that already has an override replaces it.</small></label>
          {save.isError && <StatusMessage>{getErrorMessage(save.error)}</StatusMessage>}
          <div className="form-actions">
            <button className="save-button" type="submit" disabled={save.isPending}>{save.isPending ? <LoaderCircle className="spin" size={16}/> : <CalendarPlus size={16}/>} {save.isPending ? "Saving" : "Save override"}</button>
          </div>
        </form>

        <div className="override-list">
          {overrides.isLoading && <LoaderCircle className="spin" />}
          {overrides.isError && <StatusMessage>{getErrorMessage(overrides.error)}</StatusMessage>}
          {remove.isError && <StatusMessage>{getErrorMessage(remove.error)}</StatusMessage>}
          {overrides.data?.map((item: DateOverride) => <div className={`override-row ${item.is_available ? "custom" : "blocked"}`} key={item.id}>
            <div>
              <strong>{formatDate(item.exception_date)}</strong>
              <small>{item.is_available ? `${timeValue(item.start_time)} to ${timeValue(item.end_time)}` : "Unavailable all day"}{item.note ? ` · ${item.note}` : ""}</small>
            </div>
            <button
              aria-label={`Remove override for ${formatDate(item.exception_date)}`}
              className="quiet-button"
              type="button"
              disabled={remove.isPending && remove.variables === item.exception_date}
              onClick={() => remove.mutate(item.exception_date)}
            >
              {remove.isPending && remove.variables === item.exception_date ? <LoaderCircle className="spin" size={14}/> : <Trash2 size={14}/>} Remove
            </button>
          </div>)}
          {!overrides.isLoading && !overrides.isError && !overrides.data?.length && <div className="empty-state"><CalendarOff size={18}/><p>No upcoming overrides. Your weekly hours apply every day.</p></div>}
        </div>
      </div>
    </section>
  );
}
