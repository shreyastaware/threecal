"use client";

import { useQuery } from "@tanstack/react-query";
import {
  ArrowUpRight,
  Clock3,
  LoaderCircle,
  MapPin,
  MoveRight,
} from "lucide-react";
import Link from "next/link";
import posthog from "posthog-js";

import { bookingApi, type PublicEventType } from "@/features/booking/api";
import { StatusMessage } from "@/features/dashboard/components/status-message";
import { getErrorMessage } from "@/lib/api/client";

function initials(name: string): string {
  return name
    .trim()
    .split(/\s+/)
    .slice(0, 2)
    .map((part) => part.charAt(0).toUpperCase())
    .join("");
}

function priceLabel(event: PublicEventType): string {
  if (!event.price_minor) return "Free";
  return new Intl.NumberFormat(undefined, {
    style: "currency",
    currency: event.currency,
  }).format(event.price_minor / 100);
}

export function PublicProfile({ username }: { username: string }) {
  const profile = useQuery({
    queryKey: ["public-profile", username],
    queryFn: () => bookingApi.getProfile(username),
  });

  if (profile.isLoading) {
    return (
      <main className="booking-loading">
        <LoaderCircle className="spin" /> Opening booking desk
      </main>
    );
  }
  if (profile.isError || !profile.data) {
    return (
      <main className="booking-loading">
        <StatusMessage>
          {profile.isError
            ? getErrorMessage(profile.error)
            : "This booking profile is unavailable."}
        </StatusMessage>
      </main>
    );
  }

  const { host, event_types: eventTypes } = profile.data;
  return (
    <main className="public-profile-canvas">
      <section className="public-profile-intro">
        <header>
          <span className="wordmark wordmark-light">threecal.</span>
          <span className="public-profile-index">
            PUBLIC DESK / {username.toUpperCase()}
          </span>
        </header>
        <div className="public-profile-person">
          <div className="public-profile-avatar">
            {host.avatar_url ? (
              // eslint-disable-next-line @next/next/no-img-element
              <img alt={`${host.full_name}'s profile`} src={host.avatar_url} />
            ) : (
              <span>{initials(host.full_name)}</span>
            )}
          </div>
          <p className="kicker">Book time with</p>
          <h1>{host.full_name}</h1>
          <p>{host.bio ?? "Choose the right session and a time that works."}</p>
          <small>
            <MapPin size={13} /> Working from {host.timezone}
          </small>
        </div>
        <p className="public-profile-footnote">
          Select an appointment type to see live availability.
        </p>
      </section>

      <section className="public-profile-offers">
        <header>
          <p className="kicker kicker-dark">Available appointments</p>
          <h2>
            Choose your
            <br />
            conversation.
          </h2>
          <p>Each link opens the live calendar for that appointment.</p>
        </header>
        <div className="public-profile-event-list">
          {eventTypes.map((event, index) => (
            <Link
              className="public-profile-event"
              href={`/${encodeURIComponent(username)}/${encodeURIComponent(event.slug)}`}
              key={event.id}
              onClick={() =>
                posthog.capture("public_event_type_selected", {
                  event_type_id: event.id,
                  is_paid: event.price_minor > 0,
                })
              }
            >
              <span>{String(index + 1).padStart(2, "0")}</span>
              <div>
                <h3>{event.title}</h3>
                <p>
                  {event.description ??
                    "A focused appointment shaped around your needs."}
                </p>
                <small>
                  <Clock3 size={13} /> {event.duration_minutes} min
                  <i>{priceLabel(event)}</i>
                </small>
              </div>
              <span className="public-profile-event-arrow">
                <ArrowUpRight size={20} />
              </span>
            </Link>
          ))}
          {!eventTypes.length && (
            <div className="public-profile-empty">
              <MoveRight size={20} />
              <p>No public appointment types are available yet.</p>
            </div>
          )}
        </div>
      </section>
    </main>
  );
}
