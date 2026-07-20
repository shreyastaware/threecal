"use client";

import { useQuery } from "@tanstack/react-query";
import { ArrowRight, CalendarDays, Clock3, LoaderCircle } from "lucide-react";
import { useMemo, useState } from "react";

import { apiRequest } from "@/lib/api/client";

type PageData = { host: { full_name: string; bio: string | null; timezone: string }; event_type: { title: string; description: string | null; duration_minutes: number; price_minor: number; currency: string } };
type Slot = { starts_at: string; ends_at: string };

export function PublicBooking({ username, eventSlug }: { username: string; eventSlug: string }) {
  const [selected, setSelected] = useState<string>();
  const dates = useMemo(() => { const start = new Date(); const end = new Date(); end.setDate(end.getDate() + 13); return { start: start.toISOString().slice(0, 10), end: end.toISOString().slice(0, 10) }; }, []);
  const page = useQuery({ queryKey: ["booking-page", username, eventSlug], queryFn: () => apiRequest<PageData>(`/public/${username}/${eventSlug}`) });
  const slots = useQuery({ queryKey: ["slots", username, eventSlug, dates], queryFn: () => apiRequest<Slot[]>(`/public/${username}/${eventSlug}/slots?start=${dates.start}&end=${dates.end}&timezone=${encodeURIComponent(Intl.DateTimeFormat().resolvedOptions().timeZone)}`) });
  if (page.isLoading) return <main className="booking-loading"><LoaderCircle className="spin"/>Finding open hours</main>;
  if (!page.data) return <main className="booking-loading">This booking page is unavailable.</main>;
  const grouped = Object.groupBy(slots.data ?? [], (slot) => slot.starts_at.slice(0, 10));
  return <main className="booking-canvas"><section className="booking-intro"><div><span className="wordmark wordmark-light">threecal.</span><p className="booking-number">BOOKING DESK / {username.toUpperCase()}</p></div><div className="host-copy"><p className="kicker">Appointment with</p><h1>{page.data.host.full_name}</h1><p>{page.data.host.bio ?? "Choose a considered time for a focused conversation."}</p></div><div className="event-ticket"><span>{page.data.event_type.title}</span><strong><Clock3/> {page.data.event_type.duration_minutes} min</strong><small>{page.data.event_type.price_minor ? `${page.data.event_type.currency} ${(page.data.event_type.price_minor / 100).toFixed(0)}` : "No payment required"}</small></div></section><section className="slot-desk"><header><p className="kicker kicker-dark">Select a time</p><h2>Open hours</h2><p><CalendarDays/> Shown in {Intl.DateTimeFormat().resolvedOptions().timeZone}</p></header><div className="slot-list">{Object.entries(grouped).map(([day, daySlots]) => <article key={day}><h3>{new Date(`${day}T12:00:00`).toLocaleDateString(undefined, { weekday: "short", month: "short", day: "numeric" })}</h3><div>{daySlots?.map((slot) => <button className={selected === slot.starts_at ? "chosen" : ""} onClick={() => setSelected(slot.starts_at)} key={slot.starts_at}>{new Date(slot.starts_at).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })}<ArrowRight/></button>)}</div></article>)}{!slots.isLoading && !slots.data?.length && <p>No open times in the next two weeks.</p>}</div></section></main>;
}
