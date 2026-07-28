"use client";

import { zodResolver } from "@hookform/resolvers/zod";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Check, Edit3, LoaderCircle, Plus, Route, X } from "lucide-react";
import Link from "next/link";
import posthog from "posthog-js";
import { useEffect, useState } from "react";
import { useForm } from "react-hook-form";

import { useAuth } from "@/features/auth/hooks/use-auth";
import { StatusMessage } from "@/features/dashboard/components/status-message";
import { eventTypesApi, type EventType, type EventTypeInput } from "@/features/event-types/api";
import { eventTypeSchema, type EventTypeFormValues } from "@/features/event-types/schemas";
import { getErrorMessage } from "@/lib/api/client";

const emptyValues: EventTypeFormValues = {
  title: "",
  slug: "",
  description: "",
  duration_minutes: 30,
  slot_interval_minutes: 30,
  price_minor: 0,
  currency: "INR",
  is_active: true,
  is_default: false,
};

function displayPrice(event: EventType) {
  if (!event.price_minor) return "Free";
  return new Intl.NumberFormat(undefined, { style: "currency", currency: event.currency }).format(event.price_minor / 100);
}

export function EventTypeManager() {
  const { user } = useAuth();
  const queryClient = useQueryClient();
  const events = useQuery({ queryKey: ["event-types"], queryFn: eventTypesApi.list });
  const [editing, setEditing] = useState<string | null>(null);
  const save = useMutation({
    mutationFn: ({ id, input }: { id?: string; input: EventTypeInput }) => id ? eventTypesApi.update(id, input) : eventTypesApi.create(input),
    onSuccess: (event) => {
      queryClient.setQueryData<EventType[]>(["event-types"], (current) => {
        if (!current) return [event];
        const synchronized = event.is_default
          ? current.map((item) => ({ ...item, is_default: false }))
          : current;
        return synchronized.some((item) => item.id === event.id) ? synchronized.map((item) => item.id === event.id ? event : item) : [...synchronized, event];
      });
      setEditing(null);
      reset(emptyValues);
    },
  });
  const {
    register,
    reset,
    handleSubmit,
    formState: { errors },
  } = useForm<EventTypeFormValues>({ resolver: zodResolver(eventTypeSchema), defaultValues: emptyValues });

  useEffect(() => {
    const event = events.data?.find((item) => item.id === editing);
    if (event) {
      reset({ ...event, description: event.description ?? "" });
    } else if (!editing) {
      reset(emptyValues);
    }
  }, [editing, events.data, reset]);

  const onSubmit = handleSubmit((values) => {
    const isNewEventType = !editing;
    save.mutate(
      {
        id: editing ?? undefined,
        input: { ...values, description: values.description || null, currency: values.currency.toUpperCase() },
      },
      {
        onSuccess: (event) => {
          posthog.capture(isNewEventType ? "event_type_created" : "event_type_updated", {
            duration_minutes: event.duration_minutes,
            slot_interval_minutes: event.slot_interval_minutes,
            price_minor: event.price_minor,
            currency: event.currency,
            is_active: event.is_active,
            is_default: event.is_default,
          });
        },
      },
    );
  });

  return (
    <div className="event-manager">
      <section className="workspace-panel event-form-panel">
        <div className="panel-heading">
          <div><span>{editing ? "Edit event type" : "Create an event type"}</span><h2>{editing ? "Refine the offer" : "Give time a shape"}</h2></div>
          <p>Each event type gets its own public booking link and availability rules.</p>
        </div>
        <form className="event-form" onSubmit={onSubmit} noValidate>
          <label><span>Title</span><input {...register("title")} placeholder="Advisory session" />{errors.title && <small className="field-error">{errors.title.message}</small>}</label>
          <label><span>Slug</span><input autoCapitalize="none" {...register("slug")} placeholder="advisory-session" />{errors.slug && <small className="field-error">{errors.slug.message}</small>}</label>
          <label className="event-description"><span>Description</span><textarea {...register("description")} placeholder="What should invitees expect?" />{errors.description && <small className="field-error">{errors.description.message}</small>}</label>
          <label><span>Duration (minutes)</span><input type="number" min="5" max="480" {...register("duration_minutes", { valueAsNumber: true })} />{errors.duration_minutes && <small className="field-error">{errors.duration_minutes.message}</small>}</label>
          <label><span>Slot interval (minutes)</span><input type="number" min="5" max="480" {...register("slot_interval_minutes", { valueAsNumber: true })} />{errors.slot_interval_minutes && <small className="field-error">{errors.slot_interval_minutes.message}</small>}</label>
          <label><span>Price (minor units)</span><input type="number" min="0" {...register("price_minor", { valueAsNumber: true })} /><small className="field-hint">INR 500.00 is entered as 50000.</small>{errors.price_minor && <small className="field-error">{errors.price_minor.message}</small>}</label>
          <label><span>Currency</span><input maxLength={3} {...register("currency")} />{errors.currency && <small className="field-error">{errors.currency.message}</small>}</label>
          <label className="checkbox-field"><input type="checkbox" {...register("is_active")} /><span>Visible on my booking page</span></label>
          <label className="checkbox-field default-booking-field">
            <input type="checkbox" {...register("is_default")} />
            <span>
              <strong>Use as default booking</strong>
              <small>Your main public link will open this event directly. Selecting it replaces any current default.</small>
              {errors.is_default && <small className="field-error">{errors.is_default.message}</small>}
            </span>
          </label>
          {save.isError && <StatusMessage>{getErrorMessage(save.error)}</StatusMessage>}
          <div className="form-actions">
            <button className="save-button" type="submit" disabled={save.isPending}>{save.isPending ? <LoaderCircle className="spin" size={16}/> : <Check size={16}/>} {save.isPending ? "Saving" : editing ? "Update event" : "Create event"}</button>
            {editing && <button className="quiet-button" type="button" onClick={() => setEditing(null)}><X size={15}/> Cancel</button>}
          </div>
        </form>
      </section>
      <section className="workspace-panel event-list-panel">
        <div className="panel-heading">
          <div><span>Your offers</span><h2>Event types</h2></div>
          <p>{events.data?.length ?? 0} configured event types.</p>
        </div>
        {events.isLoading && <LoaderCircle className="spin" />}
        {events.isError && <StatusMessage>{getErrorMessage(events.error)}</StatusMessage>}
        <div className="event-list">
          {events.data?.map((event) => <article className={!event.is_active ? "event-card inactive" : "event-card"} key={event.id}>
            <div><div className="event-status-row"><span className="event-status">{event.is_active ? "Live" : "Hidden"}</span>{event.is_default && <span className="event-default-status"><Route size={12}/> Default booking</span>}</div><h3>{event.title}</h3><p>{event.description || "No description yet."}</p></div>
            <div className="event-meta"><strong>{displayPrice(event)}</strong><small>{event.duration_minutes} min · every {event.slot_interval_minutes} min</small><div><button className="quiet-button" type="button" onClick={() => setEditing(event.id)}><Edit3 size={14}/> Edit</button>{user?.username && event.is_active && <Link className="text-link" href={`/${user.username}/${event.slug}`} target="_blank">Open link</Link>}</div></div>
          </article>)}
          {!events.isLoading && !events.data?.length && <div className="empty-state"><Plus size={18}/><p>Create your first event type above.</p></div>}
        </div>
      </section>
    </div>
  );
}
