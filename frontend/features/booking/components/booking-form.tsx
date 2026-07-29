"use client";

import { zodResolver } from "@hookform/resolvers/zod";
import { useMutation } from "@tanstack/react-query";
import { ArrowLeft, Check, LoaderCircle } from "lucide-react";
import posthog from "posthog-js";
import { useEffect, useState } from "react";
import { useForm } from "react-hook-form";

import { TimezoneOptions } from "@/components/timezone-options";
import { StatusMessage } from "@/features/dashboard/components/status-message";
import { bookingApi, type Booking, type PublicPage } from "@/features/booking/api";
import { bookingSchema, type BookingFormValues } from "@/features/booking/schemas";
import { ProviderCheckout } from "@/features/booking/components/provider-checkout";
import { paymentsApi, type Checkout } from "@/features/payments/api";
import { getErrorMessage } from "@/lib/api/client";

function formatSlot(value: string, timezone: string) {
  return new Intl.DateTimeFormat(undefined, { weekday: "long", month: "long", day: "numeric", hour: "numeric", minute: "2-digit", timeZone: timezone }).format(new Date(value));
}

function secondsUntil(expiresAt: string) {
  const normalized = /(?:Z|[+-]\d{2}:?\d{2})$/.test(expiresAt) ? expiresAt : `${expiresAt}Z`;
  return Math.max(0, Math.floor((new Date(normalized).getTime() - Date.now()) / 1000));
}

export function BookingForm({
  username,
  eventSlug,
  page,
  selected,
  timezone,
  onBack,
}: {
  username: string;
  eventSlug: string;
  page: PublicPage;
  selected: string;
  timezone: string;
  onBack: () => void;
}) {
  const [booking, setBooking] = useState<Booking | null>(null);
  const [checkout, setCheckout] = useState<Checkout | null>(null);
  const [now, setNow] = useState(() => Date.now());
  const create = useMutation({ mutationFn: (values: BookingFormValues) => bookingApi.create(username, eventSlug, { ...values, notes: values.notes || undefined, starts_at: selected }) });
  // The mutation error is rendered below.
  const startCheckout = useMutation({ mutationFn: paymentsApi.createCheckout, onSuccess: setCheckout });
  const { register, handleSubmit, formState: { errors, isSubmitting } } = useForm<BookingFormValues>({
    resolver: zodResolver(bookingSchema),
    defaultValues: { invitee_timezone: timezone, invitee_name: "", invitee_email: "", notes: "" },
  });

  useEffect(() => {
    if (!booking?.payment_expires_at) return;
    const interval = window.setInterval(() => setNow(Date.now()), 1000);
    return () => window.clearInterval(interval);
  }, [booking?.payment_expires_at]);

  const remaining = booking ? secondsUntil(booking.payment_expires_at) : secondsUntil(new Date(now).toISOString());

  const onSubmit = handleSubmit(async (values) => {
    const created = await create.mutateAsync(values);
    setBooking(created);
    posthog.capture("booking_created", {
      booking_status: created.status,
      is_paid: created.booking_amount > 0,
      booking_amount: created.booking_amount,
      currency: page.event_type.currency,
      event_duration_minutes: page.event_type.duration_minutes,
    });
    if (created.status === "pending") startCheckout.mutate(created.id);
  });

  if (booking?.status === "confirmed" && booking.booking_amount === 0) {
    return <section className="booking-form-card"><StatusMessage tone="success"><Check size={15}/> Your appointment is confirmed.</StatusMessage><h3>See you soon, {booking.invitee_name}.</h3><p>A confirmation has been sent to {booking.invitee_email}.</p></section>;
  }

  if (booking?.status === "pending") {
    return <section className="booking-form-card"><div className="booking-form-heading"><span className="kicker kicker-dark">Payment required</span><h3>Hold your time for 10 minutes.</h3><p>Your slot is reserved while payment is completed. <strong className={remaining < 60 ? "timer urgent" : "timer"}>{Math.floor(remaining / 60)}:{String(remaining % 60).padStart(2, "0")}</strong></p></div>{remaining === 0 ? <><StatusMessage>The payment window expired. Return to the calendar and choose another time.</StatusMessage><button className="back-button" type="button" onClick={onBack}><ArrowLeft size={15}/> Return to calendar</button></> : startCheckout.isPending ? <p className="booking-processing"><LoaderCircle className="spin"/> Preparing secure checkout</p> : checkout ? <ProviderCheckout checkout={checkout}/> : startCheckout.isError ? <><StatusMessage>{getErrorMessage(startCheckout.error)}</StatusMessage><button className="back-button" type="button" onClick={() => startCheckout.mutate(booking.id)}>Try checkout again</button></> : null}</section>;
  }

  return (
    <section className="booking-form-card">
      <button className="back-button" type="button" onClick={onBack}><ArrowLeft size={15}/> Choose another time</button>
      <div className="booking-form-heading"><span className="kicker kicker-dark">Your details</span><h3>{formatSlot(selected, timezone)}</h3><p>{page.event_type.title} · {page.event_type.duration_minutes} minutes</p></div>
      <form className="booking-form" onSubmit={onSubmit} noValidate>
        <label><span>Your name</span><input autoComplete="name" {...register("invitee_name")} />{errors.invitee_name && <small className="field-error">{errors.invitee_name.message}</small>}</label>
        <label><span>Email address</span><input type="email" autoComplete="email" {...register("invitee_email")} />{errors.invitee_email && <small className="field-error">{errors.invitee_email.message}</small>}</label>
        <label><span>Your timezone</span><select {...register("invitee_timezone")}><TimezoneOptions currentTimezone={timezone} /></select>{errors.invitee_timezone && <small className="field-error">{errors.invitee_timezone.message}</small>}</label>
        <label><span>Notes <small>(optional)</small></span><textarea {...register("notes")} placeholder="Anything useful to know?" />{errors.notes && <small className="field-error">{errors.notes.message}</small>}</label>
        {create.isError && <StatusMessage>{getErrorMessage(create.error)}</StatusMessage>}
        <button className="save-button" type="submit" disabled={isSubmitting || create.isPending}>{create.isPending ? <LoaderCircle className="spin" size={16}/> : <Check size={16}/>} {create.isPending ? "Reserving" : page.event_type.price_minor ? "Reserve and pay" : "Confirm appointment"}</button>
      </form>
    </section>
  );
}
