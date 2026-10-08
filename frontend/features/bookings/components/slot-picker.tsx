"use client";

import { useQuery } from "@tanstack/react-query";
import { ArrowLeft, ArrowRight, Check, LoaderCircle } from "lucide-react";
import { useMemo, useState } from "react";

import type { Slot } from "@/features/booking/api";
import { dateStringInTimezone, formatDayHeading, formatSlotTime, groupSlots, slotWindow } from "@/features/booking/slots";
import { StatusMessage } from "@/features/dashboard/components/status-message";
import { getErrorMessage } from "@/lib/api/client";

/** Paged slot calendar used to pick a new time when rescheduling. */
export function SlotPicker({
  queryKey,
  loadSlots,
  timezone,
  hostTimezone,
  maxDaysInAdvance,
  selected,
  onSelect,
}: {
  queryKey: readonly unknown[];
  loadSlots: (start: string, end: string, timezone: string) => Promise<Slot[]>;
  /** Timezone the slots are shown in. */
  timezone: string;
  /** Host timezone, which defines "today" for the booking window. */
  hostTimezone: string;
  maxDaysInAdvance: number | null;
  selected: string | null;
  onSelect: (startsAt: string) => void;
}) {
  const [windowIndex, setWindowIndex] = useState(0);
  const range = useMemo(
    () => slotWindow(dateStringInTimezone(new Date(), hostTimezone), windowIndex, maxDaysInAdvance),
    [hostTimezone, windowIndex, maxDaysInAdvance],
  );
  const slots = useQuery({
    queryKey: [...queryKey, range.start, range.end, timezone],
    queryFn: () => loadSlots(range.start, range.end, timezone),
  });
  const days = Object.entries(groupSlots(slots.data ?? [], timezone)).sort(([a], [b]) => a.localeCompare(b));

  return (
    <div className="reschedule-slots">
      <nav className="slot-window-nav" aria-label="Change dates">
        <button type="button" disabled={!range.hasPrevious} onClick={() => setWindowIndex((index) => Math.max(0, index - 1))}><ArrowLeft size={14}/> Earlier</button>
        <span>{formatDayHeading(range.start)} – {formatDayHeading(range.end)}</span>
        <button type="button" disabled={!range.hasNext} onClick={() => setWindowIndex((index) => index + 1)}>Later <ArrowRight size={14}/></button>
      </nav>
      <div className="slot-list reschedule-slot-list">
        {slots.isLoading && <p className="booking-processing"><LoaderCircle className="spin" size={15}/> Checking availability</p>}
        {slots.isError && <StatusMessage>{getErrorMessage(slots.error)}</StatusMessage>}
        {days.map(([day, daySlots]) => (
          <article key={day}>
            <h3>{formatDayHeading(day)}</h3>
            <div>
              {daySlots.map((slot) => {
                const chosen = slot.starts_at === selected;
                return (
                  <button className={chosen ? "slot-button chosen" : "slot-button"} type="button" aria-pressed={chosen} onClick={() => onSelect(slot.starts_at)} key={slot.starts_at}>
                    {formatSlotTime(slot.starts_at, timezone)}{chosen && <Check size={13}/>}
                  </button>
                );
              })}
            </div>
          </article>
        ))}
        {!slots.isLoading && !slots.isError && !days.length && <p className="form-hint">No open times in these dates.</p>}
      </div>
    </div>
  );
}
