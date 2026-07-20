"use client";

import { useMutation, useQuery } from "@tanstack/react-query";
import { Check, LoaderCircle } from "lucide-react";
import { useState } from "react";

import { schedulingApi, type WorkingHour } from "@/features/scheduling/api";

const DAYS = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"];
const defaults: WorkingHour[] = DAYS.map((_, weekday) => ({ weekday, start_time: "09:00", end_time: "17:00", is_enabled: weekday < 5, breaks: [] }));

export function ScheduleEditor() {
  const schedule = useQuery({ queryKey: ["availability"], queryFn: schedulingApi.getSchedule });
  const [editedHours, setEditedHours] = useState<WorkingHour[] | null>(null);
  const hours = editedHours ?? (schedule.data?.length ? defaults.map((item) => schedule.data?.find((row) => row.weekday === item.weekday) ?? item) : defaults);
  const save = useMutation({ mutationFn: schedulingApi.saveSchedule });

  function patch(day: number, values: Partial<WorkingHour>) {
    setEditedHours(hours.map((item) => item.weekday === day ? { ...item, ...values } : item));
  }

  return (
    <section className="workspace-panel">
      <div className="panel-heading"><div><span>02 / Availability</span><h2>Your working rhythm</h2></div><p>Times are saved in your profile timezone.</p></div>
      <div className="schedule-grid">
        {hours.map((item) => <div className={`schedule-row ${item.is_enabled ? "active" : ""}`} key={item.weekday}>
          <label className="day-switch"><input type="checkbox" checked={item.is_enabled} onChange={(event) => patch(item.weekday, { is_enabled: event.target.checked })}/><i/><strong>{DAYS[item.weekday]}</strong></label>
          {item.is_enabled ? <div className="time-pair"><input aria-label={`${DAYS[item.weekday]} start`} type="time" value={item.start_time.slice(0, 5)} onChange={(event) => patch(item.weekday, { start_time: event.target.value })}/><span>to</span><input aria-label={`${DAYS[item.weekday]} end`} type="time" value={item.end_time.slice(0, 5)} onChange={(event) => patch(item.weekday, { end_time: event.target.value })}/></div> : <em>Unavailable</em>}
        </div>)}
      </div>
      <button className="save-button" onClick={() => save.mutate(hours)} disabled={save.isPending}>{save.isPending ? <LoaderCircle className="spin" size={16}/> : <Check size={16}/>} {save.isSuccess ? "Schedule saved" : "Save availability"}</button>
    </section>
  );
}
