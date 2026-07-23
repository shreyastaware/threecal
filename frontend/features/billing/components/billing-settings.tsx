"use client";

import { zodResolver } from "@hookform/resolvers/zod";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { ArrowRight, Check, ExternalLink, LoaderCircle } from "lucide-react";
import posthog from "posthog-js";
import { useForm } from "react-hook-form";

import { StatusMessage } from "@/features/dashboard/components/status-message";
import { billingApi } from "@/features/billing/api";
import { billingCompleteSchema, type BillingCompleteFormValues } from "@/features/billing/schemas";
import { getErrorMessage } from "@/lib/api/client";

function formatInr(minor: number) {
  return new Intl.NumberFormat("en-IN", { style: "currency", currency: "INR" }).format(minor / 100);
}

export function BillingSettings() {
  const queryClient = useQueryClient();
  const billing = useQuery({ queryKey: ["billing"], queryFn: billingApi.get });
  const { register, reset, handleSubmit, formState: { errors } } = useForm<BillingCompleteFormValues>({ resolver: zodResolver(billingCompleteSchema) });
  const start = useMutation({
    mutationFn: billingApi.startSetup,
    onSuccess: ({ checkout_url }) => {
      posthog.capture("billing_setup_started");
      window.location.assign(checkout_url);
    },
  });
  const complete = useMutation({
    mutationFn: billingApi.completeSetup,
    onSuccess: (updated) => {
      queryClient.setQueryData(["billing"], updated);
      posthog.capture("billing_mandate_verified");
      reset();
    },
  });

  const onSubmit = handleSubmit((values) => complete.mutate(values));

  if (billing.isLoading) return <section className="workspace-panel"><LoaderCircle className="spin" /> Loading platform billing</section>;
  if (billing.isError) return <section className="workspace-panel"><StatusMessage>{getErrorMessage(billing.error)}</StatusMessage></section>;

  return (
    <section className="workspace-panel billing-panel">
      <div className="panel-heading">
        <div><span>Platform billing</span><h2>Keep paid bookings open</h2></div>
        <p>Threecal charges a monthly volume-based platform fee. Your recurring mandate is required before paid events can accept bookings.</p>
      </div>
      <div className="billing-body">
        <div className={`billing-status ${billing.data?.ready ? "ready" : "needs-setup"}`}><span>{billing.data?.ready ? "Ready for paid bookings" : "Setup required"}</span><strong>{formatInr(billing.data?.current_cycle_earnings ?? 0)}</strong><small>Current cycle earnings</small></div>
        {!billing.data?.ready && <div className="billing-actions">
          <p>Start the Dodo Payments mandate checkout. After it completes, enter the payment method and subscription IDs from the checkout flow to verify ownership.</p>
          {start.isError && <StatusMessage>{getErrorMessage(start.error)}</StatusMessage>}
          <button className="save-button" type="button" disabled={start.isPending} onClick={() => start.mutate()}>{start.isPending ? <LoaderCircle className="spin" size={16}/> : <ExternalLink size={16}/>} Start billing setup</button>
        </div>}
        <form className="billing-complete-form" onSubmit={onSubmit} noValidate>
          <div><span className="form-section-label">Complete a returned checkout</span><p>Use these fields only after Dodo has returned the IDs.</p></div>
          <label><span>Payment method ID</span><input {...register("payment_method_id")} />{errors.payment_method_id && <small className="field-error">{errors.payment_method_id.message}</small>}</label>
          <label><span>Subscription ID</span><input {...register("subscription_id")} />{errors.subscription_id && <small className="field-error">{errors.subscription_id.message}</small>}</label>
          {complete.isError && <StatusMessage>{getErrorMessage(complete.error)}</StatusMessage>}
          {complete.isSuccess && <StatusMessage tone="success"><Check size={14}/> Billing mandate verified.</StatusMessage>}
          <button className="save-button" type="submit" disabled={complete.isPending}>{complete.isPending ? <LoaderCircle className="spin" size={16}/> : <ArrowRight size={16}/>} Verify mandate</button>
        </form>
      </div>
    </section>
  );
}
