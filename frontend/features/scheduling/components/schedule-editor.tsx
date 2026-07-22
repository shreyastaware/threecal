"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Check, LoaderCircle, Plus, Trash2 } from "lucide-react";
import { useState } from "react";

import { StatusMessage } from "@/features/dashboard/components/status-message";
import { schedulingApi, type WorkingHour } from "@/features/scheduling/api";
import { scheduleSchema } from "@/features/scheduling/schemas";
import { getErrorMessage } from "@/lib/api/client";

const DAYS = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"];
const defaults: WorkingHour[] = DAYS.map((_, weekday) => ({ weekday, start_time: "09:00", end_time: "17:00", is_enabled: weekday < 5, breaks: [] }));

function normalizeHours(rows: WorkingHour[]): WorkingHour[] {
  return defaults.map((item) => rows.find((row) => row.weekday === item.weekday) ?? item);
}

function timeValue(value: string) {
  return value.slice(0, 5);
}

export function ScheduleEditor() {
  const schedule = useQuery({ queryKey: ["availability"], queryFn: schedulingApi.getSchedule });
  const queryClient = useQueryClient();
  const [editedHours, setEditedHours] = useState<WorkingHour[] | null>(null);
  const [validationError, setValidationError] = useState<string | null>(null);
  const hours = editedHours ?? (schedule.data ? normalizeHours(schedule.data) : defaults);
  const save = useMutation({ mutationFn: schedulingApi.saveSchedule });

  function patch(day: number, values: Partial<WorkingHour>) {
    setValidationError(null);
    save.reset();
    setEditedHours(hours.map((item) => item.weekday === day ? { ...item, ...values } : item));
  }

  function addBreak(day: number) {
    const row = hours.find((item) => item.weekday === day);
    if (!row) return;
    patch(day, { breaks: [...row.breaks, { start_time: "12:00", end_time: "13:00" }] });
  }

  function patchBreak(day: number, breakIndex: number, values: Partial<WorkingHour["breaks"][number]>) {
    const row = hours.find((item) => item.weekday === day);
    if (!row) return;
    patch(day, { breaks: row.breaks.map((pause, index) => index === breakIndex ? { ...pause, ...values } : pause) });
  }

  function removeBreak(day: number, breakIndex: number) {
    const row = hours.find((item) => item.weekday === day);
    if (!row) return;
    patch(day, { breaks: row.breaks.filter((_, index) => index !== breakIndex) });
  }

  function saveHours() {
    const result = scheduleSchema.safeParse(hours);
    if (!result.success) {
      setValidationError(result.error.issues[0]?.message ?? "Check the schedule values.");
      return;
    }
    setValidationError(null);
    save.mutate(result.data, { onSuccess: (updated) => { setEditedHours(normalizeHours(updated)); queryClient.setQueryData(["availability"], updated); } });
  }

  if (schedule.isLoading) return <section className="workspace-panel"><div className="panel-heading"><span>02 / Availability</span><h2>Loading your rhythm</h2></div><LoaderCircle className="spin" /></section>;
  if (schedule.isError) return <section className="workspace-panel"><div className="panel-heading"><span>02 / Availability</span><h2>Could not load availability</h2></div><StatusMessage>{getErrorMessage(schedule.error)}</StatusMessage></section>;

  return (
    <section className="workspace-panel">
      <div className="panel-heading"><div><span>02 / Availability</span><h2>Your working rhythm</h2></div><p>Times are saved in your profile timezone.</p></div>
      <div className="schedule-grid">
        {hours.map((item) => <div className={`schedule-row ${item.is_enabled ? "active" : ""}`} key={item.weekday}>
          <div className="schedule-row-main">
            <label className="day-switch"><input type="checkbox" checked={item.is_enabled} onChange={(event) => patch(item.weekday, { is_enabled: event.target.checked })}/><i/><strong>{DAYS[item.weekday]}</strong></label>
            {item.is_enabled ? <div className="time-pair"><input aria-label={`${DAYS[item.weekday]} start`} type="time" value={timeValue(item.start_time)} onChange={(event) => patch(item.weekday, { start_time: event.target.value })}/><span>to</span><input aria-label={`${DAYS[item.weekday]} end`} type="time" value={timeValue(item.end_time)} onChange={(event) => patch(item.weekday, { end_time: event.target.value })}/></div> : <em>Unavailable</em>}
          </div>
          {item.is_enabled && <div className="break-list">
            {item.breaks.map((pause, index) => <div className="break-row" key={`${item.weekday}-${index}`}>
              <span>Break</span>
              <input aria-label={`${DAYS[item.weekday]} break start`} type="time" value={timeValue(pause.start_time)} onChange={(event) => patchBreak(item.weekday, index, { start_time: event.target.value })}/>
              <span>to</span>
              <input aria-label={`${DAYS[item.weekday]} break end`} type="time" value={timeValue(pause.end_time)} onChange={(event) => patchBreak(item.weekday, index, { end_time: event.target.value })}/>
              <button aria-label={`Remove ${DAYS[item.weekday]} break`} type="button" onClick={() => removeBreak(item.weekday, index)}><Trash2 size={14}/></button>
            </div>)}
            <button className="break-add" type="button" onClick={() => addBreak(item.weekday)}><Plus size={14}/> Add break</button>
          </div>}
        </div>)}
      </div>
      {validationError && <StatusMessage>{validationError}</StatusMessage>}
      {save.isError && <StatusMessage>{getErrorMessage(save.error)}</StatusMessage>}
      {save.isSuccess && <StatusMessage tone="success">Availability saved.</StatusMessage>}
      <button className="save-button" type="button" onClick={saveHours} disabled={save.isPending}>{save.isPending ? <LoaderCircle className="spin" size={16}/> : <Check size={16}/>} {save.isPending ? "Saving" : "Save availability"}</button>
    </section>
  );
}
