"use client";

import { Dialog } from "@base-ui/react/dialog";
import { zodResolver } from "@hookform/resolvers/zod";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Check, Edit3, LoaderCircle, Plus, Route, Trash2, TriangleAlert, X } from "lucide-react";
import Link from "next/link";
import posthog from "posthog-js";
import { useEffect, useState } from "react";
import { useForm, useWatch } from "react-hook-form";

import { useAuth } from "@/features/auth/hooks/use-auth";
import { StatusMessage } from "@/features/dashboard/components/status-message";
import { eventTypesApi, type EventType, type EventTypeInput } from "@/features/event-types/api";
import { eventTypeSchema, type EventTypeFormValues } from "@/features/event-types/schemas";
import { getErrorMessage } from "@/lib/api/client";

const emptyValues: EventTypeFormValues = {
  title: "",
  description: "",
  duration_option: "30",
  custom_duration_minutes: undefined,
  slot_interval_minutes: 30,
  price: 0,
  is_active: true,
  is_default: false,
};

function getDurationOption(
  durationMinutes: number,
): EventTypeFormValues["duration_option"] {
  if (
    durationMinutes === 15
    || durationMinutes === 30
    || durationMinutes === 45
    || durationMinutes === 60
  ) {
    return String(durationMinutes) as EventTypeFormValues["duration_option"];
  }
  return "custom";
}

function eventToFormValues(event: EventType): EventTypeFormValues {
  const durationOption = getDurationOption(event.duration_minutes);
  return {
    title: event.title,
    description: event.description ?? "",
    duration_option: durationOption,
    custom_duration_minutes: durationOption === "custom"
      ? event.duration_minutes
      : undefined,
    slot_interval_minutes: event.slot_interval_minutes,
    price: event.price_minor / 100,
    is_active: event.is_active,
    is_default: event.is_default,
  };
}

function displayPrice(event: EventType) {
  if (!event.price_minor) return "Free";
  return new Intl.NumberFormat(undefined, { style: "currency", currency: event.currency }).format(event.price_minor / 100);
}

export function EventTypeManager() {
  const { user } = useAuth();
  const queryClient = useQueryClient();
  const events = useQuery({ queryKey: ["event-types"], queryFn: eventTypesApi.list });
  const [editing, setEditing] = useState<string | null>(null);
  const [editorOpen, setEditorOpen] = useState(false);
  const [deleting, setDeleting] = useState<EventType | null>(null);
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
      setEditorOpen(false);
      reset(emptyValues);
    },
  });
  const remove = useMutation({
    mutationFn: eventTypesApi.delete,
    onSuccess: (_, eventId) => {
      queryClient.setQueryData<EventType[]>(["event-types"], (current) =>
        current?.filter((event) => event.id !== eventId) ?? [],
      );
      posthog.capture("event_type_deleted", { event_type_id: eventId });
      setDeleting(null);
    },
  });
  const {
    register,
    reset,
    handleSubmit,
    control,
    formState: { errors },
  } = useForm<EventTypeFormValues>({ resolver: zodResolver(eventTypeSchema), defaultValues: emptyValues });
  const selectedDuration = useWatch({ control, name: "duration_option" });

  useEffect(() => {
    const event = events.data?.find((item) => item.id === editing);
    if (event) {
      reset(eventToFormValues(event));
    } else if (!editing) {
      reset(emptyValues);
    }
  }, [editing, events.data, reset]);

  const onSubmit = handleSubmit((values) => {
    const isNewEventType = !editing;
    const {
      custom_duration_minutes: customDurationMinutes,
      duration_option: durationOption,
      price,
      ...eventTypeValues
    } = values;
    const durationMinutes = durationOption === "custom"
      ? customDurationMinutes!
      : Number(durationOption);
    save.mutate(
      {
        id: editing ?? undefined,
        input: {
          ...eventTypeValues,
          description: values.description || null,
          duration_minutes: durationMinutes,
          price_minor: Math.round(price * 100),
          currency: "INR",
        },
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

  function openCreateDialog() {
    setEditing(null);
    reset(emptyValues);
    save.reset();
    setEditorOpen(true);
  }

  function openEditDialog(eventId: string) {
    setEditing(eventId);
    save.reset();
    setEditorOpen(true);
  }

  function handleEditorOpenChange(open: boolean) {
    if (save.isPending) return;
    setEditorOpen(open);
    if (!open) {
      setEditing(null);
      reset(emptyValues);
      save.reset();
    }
  }

  function openDeleteDialog(event: EventType) {
    remove.reset();
    setDeleting(event);
  }

  function handleDeleteOpenChange(open: boolean) {
    if (remove.isPending) return;
    if (!open) {
      setDeleting(null);
      remove.reset();
    }
  }

  return (
    <div className="event-manager">
      <section className="workspace-panel event-list-panel">
        <div className="panel-heading event-list-heading">
          <div><span>Your offers</span><h2>Event types</h2></div>
          <p>{events.data?.length ?? 0} configured event types.</p>
          <button className="event-create-button" type="button" onClick={openCreateDialog}><Plus aria-hidden="true" size={16}/> Create</button>
        </div>
        {events.isLoading && <LoaderCircle className="spin" />}
        {events.isError && <StatusMessage>{getErrorMessage(events.error)}</StatusMessage>}
        <div className="event-list">
          {events.data?.map((event) => <article className={!event.is_active ? "event-card inactive" : "event-card"} key={event.id}>
            <div><div className="event-status-row"><span className="event-status">{event.is_active ? "Live" : "Hidden"}</span>{event.is_default && <span className="event-default-status"><Route size={12}/> Default booking</span>}</div><h3>{event.title}</h3><p>{event.description || "No description yet."}</p></div>
            <div className="event-meta"><strong>{displayPrice(event)}</strong><small>{event.duration_minutes} min · every {event.slot_interval_minutes} min</small><div><button className="quiet-button" type="button" onClick={() => openEditDialog(event.id)}><Edit3 size={14}/> Edit</button><button aria-label={`Delete ${event.title}`} className="quiet-button event-delete-trigger" type="button" onClick={() => openDeleteDialog(event)}><Trash2 size={14}/> Delete</button>{user?.username && event.is_active && <Link className="text-link" href={`/${user.username}/${event.slug}`} target="_blank">Open link</Link>}</div></div>
          </article>)}
          {!events.isLoading && !events.data?.length && <div className="empty-state"><Plus size={18}/><p>Create your first event type to start accepting bookings.</p></div>}
        </div>
      </section>

      <Dialog.Root onOpenChange={handleEditorOpenChange} open={editorOpen}>
        <Dialog.Portal>
          <Dialog.Backdrop className="profile-dialog-backdrop" />
          <Dialog.Viewport className="profile-dialog-viewport event-dialog-viewport">
            <Dialog.Popup className="profile-dialog-popup event-dialog-popup">
              <div className="profile-dialog-header">
                <div>
                  <p className="kicker kicker-dark">{editing ? "Edit event type" : "New event type"}</p>
                  <Dialog.Title>{editing ? "Refine the offer" : "Create an event type"}</Dialog.Title>
                  <Dialog.Description>Each event type gets its own public booking link and availability rules.</Dialog.Description>
                </div>
                <Dialog.Close aria-label="Close event type dialog" className="profile-dialog-close" disabled={save.isPending}>
                  <X size={18} />
                </Dialog.Close>
              </div>

              <form className="event-form event-dialog-form" onSubmit={onSubmit} noValidate>
                <label><span>Title</span><input {...register("title")} placeholder="Advisory session" />{errors.title && <small className="field-error">{errors.title.message}</small>}</label>
                <label>
                  <span>Duration</span>
                  <select {...register("duration_option")}>
                    <option value="15">15 min</option>
                    <option value="30">30 min</option>
                    <option value="45">45 min</option>
                    <option value="60">60 min</option>
                    <option value="custom">Custom</option>
                  </select>
                  <small className="field-hint">The booking URL is generated automatically from the duration, for example /30min.</small>
                </label>
                {selectedDuration === "custom" && (
                  <label>
                    <span>Custom duration (minutes)</span>
                    <input
                      type="number"
                      inputMode="numeric"
                      min="5"
                      max="480"
                      step="1"
                      placeholder="90"
                      {...register("custom_duration_minutes", {
                        setValueAs: (value) => value === "" ? undefined : Number(value),
                      })}
                    />
                    {errors.custom_duration_minutes && <small className="field-error">{errors.custom_duration_minutes.message}</small>}
                  </label>
                )}
                <label className="event-description"><span>Description</span><textarea {...register("description")} placeholder="What should invitees expect?" />{errors.description && <small className="field-error">{errors.description.message}</small>}</label>
                <label><span>Slot Time (minutes)</span><input type="number" min="5" max="480" {...register("slot_interval_minutes", { valueAsNumber: true })} />{errors.slot_interval_minutes && <small className="field-error">{errors.slot_interval_minutes.message}</small>}</label>
                <label><span>Price (INR)</span><input type="number" inputMode="numeric" min="0" step="1" placeholder="500" {...register("price", { valueAsNumber: true })} /><small className="field-hint">Enter a whole-number amount with no decimal places.</small>{errors.price && <small className="field-error">{errors.price.message}</small>}</label>
                <label className="event-readonly-field"><span>Currency</span><input aria-readonly="true" readOnly value="INR" /><small className="field-hint">Event type prices are currently charged in INR.</small></label>
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
                <div className="form-actions profile-dialog-actions">
                  <Dialog.Close className="profile-dialog-cancel" disabled={save.isPending}>Cancel</Dialog.Close>
                  <button className="save-button" type="submit" disabled={save.isPending}>{save.isPending ? <LoaderCircle className="spin" size={16}/> : <Check size={16}/>} {save.isPending ? "Saving" : editing ? "Update event" : "Create event"}</button>
                </div>
              </form>
            </Dialog.Popup>
          </Dialog.Viewport>
        </Dialog.Portal>
      </Dialog.Root>

      <Dialog.Root onOpenChange={handleDeleteOpenChange} open={Boolean(deleting)}>
        <Dialog.Portal>
          <Dialog.Backdrop className="profile-dialog-backdrop" />
          <Dialog.Viewport className="profile-dialog-viewport">
            <Dialog.Popup className="profile-dialog-popup event-delete-popup">
              <div className="profile-dialog-header">
                <div>
                  <p className="kicker kicker-dark">Delete event type</p>
                  <Dialog.Title>Remove this offer?</Dialog.Title>
                  <Dialog.Description>This action removes the event type from your workspace and disables its public booking link.</Dialog.Description>
                </div>
                <Dialog.Close aria-label="Close delete event dialog" className="profile-dialog-close" disabled={remove.isPending}>
                  <X size={18} />
                </Dialog.Close>
              </div>

              {deleting && (
                <div className="event-delete-summary">
                  <span><TriangleAlert aria-hidden="true" size={20} /></span>
                  <div>
                    <strong>{deleting.title}</strong>
                    <p>Existing appointment records stay intact. People will no longer be able to book this event.</p>
                  </div>
                </div>
              )}
              {remove.isError && <StatusMessage>{getErrorMessage(remove.error)}</StatusMessage>}
              <div className="profile-dialog-actions">
                <Dialog.Close className="profile-dialog-cancel" disabled={remove.isPending}>Keep event</Dialog.Close>
                <button
                  className="event-delete-confirm"
                  type="button"
                  disabled={remove.isPending || !deleting}
                  onClick={() => deleting && remove.mutate(deleting.id)}
                >
                  {remove.isPending ? <LoaderCircle className="spin" size={16} /> : <Trash2 size={16} />}
                  {remove.isPending ? "Deleting" : "Delete event"}
                </button>
              </div>
            </Dialog.Popup>
          </Dialog.Viewport>
        </Dialog.Portal>
      </Dialog.Root>
    </div>
  );
}
