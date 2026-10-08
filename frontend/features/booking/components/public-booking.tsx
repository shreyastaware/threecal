"use client";

import { useQuery } from "@tanstack/react-query";
import { ArrowLeft, ArrowRight, CalendarDays, Clock3, LoaderCircle, MapPin } from "lucide-react";
import posthog from "posthog-js";
import { useMemo, useState } from "react";

import { StatusMessage } from "@/features/dashboard/components/status-message";
import { bookingApi } from "@/features/booking/api";
import { BookingForm } from "@/features/booking/components/booking-form";
import { dateStringInTimezone, formatDayHeading, formatSlotTime, groupSlots, slotWindow } from "@/features/booking/slots";
import { publicLocationLabel } from "@/features/event-types/locations";
import { getErrorMessage } from "@/lib/api/client";

function priceLabel(priceMinor: number, currency: string) {
  if (!priceMinor) return "No payment required";
  return new Intl.NumberFormat(undefined, { style: "currency", currency }).format(priceMinor / 100);
}

export function PublicBooking({ username, eventSlug }: { username: string; eventSlug: string }) {
  const [selected, setSelected] = useState<string | null>(null);
  const [windowIndex, setWindowIndex] = useState(0);
  const [viewerTimezone] = useState(() => Intl.DateTimeFormat().resolvedOptions().timeZone || "UTC");
  const page = useQuery({ queryKey: ["booking-page", username, eventSlug], queryFn: () => bookingApi.getPage(username, eventSlug) });
  const hostTimezone = page.data?.host.timezone ?? viewerTimezone;
  const maxDaysInAdvance = page.data?.event_type.max_days_in_advance;
  // Page through the event type's booking window two weeks at a time.
  const slotRange = useMemo(
    () => slotWindow(dateStringInTimezone(new Date(), hostTimezone), windowIndex, maxDaysInAdvance),
    [hostTimezone, windowIndex, maxDaysInAdvance],
  );
  const dates = useMemo(() => ({ start: slotRange.start, end: slotRange.end }), [slotRange.start, slotRange.end]);
  const slots = useQuery({
    queryKey: ["slots", username, eventSlug, dates, viewerTimezone, hostTimezone],
    queryFn: () => bookingApi.getSlots(username, eventSlug, dates.start, dates.end, viewerTimezone),
    enabled: Boolean(page.data),
  });

  if (page.isLoading) return <main className="booking-loading"><LoaderCircle className="spin"/> Finding open hours</main>;
  if (page.isError || !page.data) return <main className="booking-loading"><StatusMessage>{page.isError ? getErrorMessage(page.error) : "This booking page is unavailable."}</StatusMessage></main>;

  const grouped = groupSlots(slots.data ?? [], viewerTimezone);
  const days = Object.entries(grouped).sort(([a], [b]) => a.localeCompare(b));
  return (
    <main className="booking-canvas">
      <section className="booking-intro">
        <div><span className="wordmark wordmark-light">threecal.</span><p className="booking-number">BOOKING DESK / {username.toUpperCase()}</p></div>
        <div className="host-copy">
          <p className="kicker">Appointment with</p>
          {page.data.host.avatar_url && (
            // Profile images are already normalized and optimized by the backend.
            // eslint-disable-next-line @next/next/no-img-element
            <img className="host-avatar" src={page.data.host.avatar_url} alt="" width={64} height={64} />
          )}
          <h1>{page.data.host.full_name}</h1>
          <p>{page.data.host.bio ?? "Choose a considered time for a focused conversation."}</p>
          <small className="host-timezone"><MapPin size={14}/> Host timezone: {page.data.host.timezone}</small>
        </div>
        <div className="event-ticket"><span>{page.data.event_type.title}</span><strong><Clock3/> {page.data.event_type.duration_minutes} min</strong><small>{priceLabel(page.data.event_type.price_minor, page.data.event_type.currency)}</small>{publicLocationLabel(page.data.event_type.location_type, page.data.event_type.location_value) && <small className="event-location"><MapPin size={12}/> {publicLocationLabel(page.data.event_type.location_type, page.data.event_type.location_value)}</small>}</div>
      </section>
      <section className="slot-desk">
        <header><p className="kicker kicker-dark">Select a time</p><h2>{selected ? "Almost there" : "Open hours"}</h2><p><CalendarDays/> Shown in {viewerTimezone}</p>{page.data.event_type.description && <p className="event-public-description">{page.data.event_type.description}</p>}</header>
        {selected ? <BookingForm username={username} eventSlug={eventSlug} page={page.data} selected={selected} timezone={viewerTimezone} onBack={() => setSelected(null)} /> : <div className="slot-list">
          {slots.isLoading && <p className="booking-processing"><LoaderCircle className="spin"/> Checking availability</p>}
          {slots.isError && <StatusMessage>{getErrorMessage(slots.error)}</StatusMessage>}
          {days.map(([day, daySlots]) => <article key={day}><h3>{formatDayHeading(day)}</h3><div>{daySlots.map((slot) => <button className="slot-button" type="button" onClick={() => { posthog.capture("booking_slot_selected", { event_duration_minutes: page.data.event_type.duration_minutes, is_paid: page.data.event_type.price_minor > 0 }); setSelected(slot.starts_at); }} key={slot.starts_at}>{formatSlotTime(slot.starts_at, viewerTimezone)}<ArrowRight/></button>)}</div></article>)}
          {!slots.isLoading && !slots.isError && !slots.data?.length && <p>{slotRange.hasNext ? "No open times in these dates." : "No open times left in the booking window."}</p>}
          {(slotRange.hasPrevious || slotRange.hasNext) && <nav className="slot-window-nav" aria-label="Change dates">
            <button type="button" disabled={!slotRange.hasPrevious} onClick={() => setWindowIndex((index) => Math.max(0, index - 1))}><ArrowLeft size={14}/> Earlier dates</button>
            <span>{formatDayHeading(slotRange.start)} – {formatDayHeading(slotRange.end)}</span>
            <button type="button" disabled={!slotRange.hasNext} onClick={() => setWindowIndex((index) => index + 1)}>Later dates <ArrowRight size={14}/></button>
          </nav>}
        </div>}
      </section>
    </main>
  );
}
