"use client";

import { useQuery } from "@tanstack/react-query";
import { ArrowRight, CalendarDays, Clock3, LoaderCircle, MapPin } from "lucide-react";
import Image from "next/image";
import { useMemo, useState } from "react";

import { StatusMessage } from "@/features/dashboard/components/status-message";
import { bookingApi, type Slot } from "@/features/booking/api";
import { BookingForm } from "@/features/booking/components/booking-form";
import { getErrorMessage } from "@/lib/api/client";

function dateStringInTimezone(date: Date, timezone: string) {
  const parts = new Intl.DateTimeFormat("en-CA", { timeZone: timezone, year: "numeric", month: "2-digit", day: "2-digit" }).formatToParts(date);
  const values = Object.fromEntries(parts.map((part) => [part.type, part.value]));
  return `${values.year}-${values.month}-${values.day}`;
}

function groupSlots(slots: Slot[], timezone: string) {
  return slots.reduce<Record<string, Slot[]>>((groups, slot) => {
    const parts = new Intl.DateTimeFormat("en-CA", { timeZone: timezone, year: "numeric", month: "2-digit", day: "2-digit" }).formatToParts(new Date(slot.starts_at));
    const value = Object.fromEntries(parts.map((part) => [part.type, part.value]));
    const day = `${value.year}-${value.month}-${value.day}`;
    groups[day] = [...(groups[day] ?? []), slot];
    return groups;
  }, {});
}

function priceLabel(priceMinor: number, currency: string) {
  if (!priceMinor) return "No payment required";
  return new Intl.NumberFormat(undefined, { style: "currency", currency }).format(priceMinor / 100);
}

export function PublicBooking({ username, eventSlug }: { username: string; eventSlug: string }) {
  const [selected, setSelected] = useState<string | null>(null);
  const [viewerTimezone] = useState(() => Intl.DateTimeFormat().resolvedOptions().timeZone || "UTC");
  const page = useQuery({ queryKey: ["booking-page", username, eventSlug], queryFn: () => bookingApi.getPage(username, eventSlug) });
  const hostTimezone = page.data?.host.timezone ?? viewerTimezone;
  const dates = useMemo(() => {
    const start = dateStringInTimezone(new Date(), hostTimezone);
    const end = new Date(`${start}T12:00:00Z`);
    end.setUTCDate(end.getUTCDate() + 13);
    return { start, end: dateStringInTimezone(end, "UTC") };
  }, [hostTimezone]);
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
          {page.data.host.avatar_url && <Image className="host-avatar" src={page.data.host.avatar_url} alt="" width={64} height={64} unoptimized />}
          <h1>{page.data.host.full_name}</h1>
          <p>{page.data.host.bio ?? "Choose a considered time for a focused conversation."}</p>
          <small className="host-timezone"><MapPin size={14}/> Host timezone: {page.data.host.timezone}</small>
        </div>
        <div className="event-ticket"><span>{page.data.event_type.title}</span><strong><Clock3/> {page.data.event_type.duration_minutes} min</strong><small>{priceLabel(page.data.event_type.price_minor, page.data.event_type.currency)}</small></div>
      </section>
      <section className="slot-desk">
        <header><p className="kicker kicker-dark">Select a time</p><h2>{selected ? "Almost there" : "Open hours"}</h2><p><CalendarDays/> Shown in {viewerTimezone}</p>{page.data.event_type.description && <p className="event-public-description">{page.data.event_type.description}</p>}</header>
        {selected ? <BookingForm username={username} eventSlug={eventSlug} page={page.data} selected={selected} timezone={viewerTimezone} onBack={() => setSelected(null)} /> : <div className="slot-list">
          {slots.isLoading && <p className="booking-processing"><LoaderCircle className="spin"/> Checking availability</p>}
          {slots.isError && <StatusMessage>{getErrorMessage(slots.error)}</StatusMessage>}
          {days.map(([day, daySlots]) => <article key={day}><h3>{new Date(`${day}T12:00:00`).toLocaleDateString(undefined, { weekday: "short", month: "short", day: "numeric" })}</h3><div>{daySlots.map((slot) => <button className="slot-button" type="button" onClick={() => setSelected(slot.starts_at)} key={slot.starts_at}>{new Date(slot.starts_at).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit", timeZone: viewerTimezone })}<ArrowRight/></button>)}</div></article>)}
          {!slots.isLoading && !slots.isError && !slots.data?.length && <p>No open times in the next two weeks.</p>}
        </div>}
      </section>
    </main>
  );
}
