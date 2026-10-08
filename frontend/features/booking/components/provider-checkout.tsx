"use client";

import { ArrowRight, Check, LoaderCircle } from "lucide-react";
import posthog from "posthog-js";
import { useEffect, useRef, useState } from "react";

import { StatusMessage } from "@/features/dashboard/components/status-message";
import { paymentsApi, type Checkout } from "@/features/payments/api";
import { getErrorMessage } from "@/lib/api/client";

const RAZORPAY_CHECKOUT_SRC = "https://checkout.razorpay.com/v1/checkout.js";

type RazorpaySuccess = {
  razorpay_payment_id: string;
  razorpay_order_id: string;
  razorpay_signature: string;
};
type RazorpayFailure = { error?: { description?: string } };
type RazorpayOptions = {
  key: string;
  amount: number;
  currency: string;
  name: string;
  description: string;
  order_id: string;
  prefill: { name: string; email: string };
  notes: Record<string, string>;
  handler: (response: RazorpaySuccess) => void;
  modal?: { ondismiss?: () => void };
};
type RazorpayClient = {
  open: () => void;
  on: (event: "payment.failed", callback: (response: RazorpayFailure) => void) => void;
};

declare global {
  interface Window {
    Razorpay?: new (options: RazorpayOptions) => RazorpayClient;
  }
}

function loadScript(src: string) {
  return new Promise<void>((resolve, reject) => {
    const existing = document.querySelector(`script[src="${src}"]`);
    if (existing) {
      resolve();
      return;
    }
    const script = document.createElement("script");
    script.src = src;
    script.async = true;
    script.onload = () => resolve();
    script.onerror = () => reject(new Error("The payment provider could not be loaded."));
    document.head.appendChild(script);
  });
}

export function ProviderCheckout({
  checkout,
  onConfirmed,
}: {
  checkout: Checkout;
  onConfirmed: () => void;
}) {
  const [error, setError] = useState<string | null>(null);
  const [message, setMessage] = useState<string | null>(null);
  const [ready, setReady] = useState(false);
  const [verifying, setVerifying] = useState(false);
  const onConfirmedRef = useRef(onConfirmed);

  useEffect(() => {
    onConfirmedRef.current = onConfirmed;
  }, [onConfirmed]);

  useEffect(() => {
    let cancelled = false;
    loadScript(RAZORPAY_CHECKOUT_SRC)
      .then(() => {
        if (!window.Razorpay) throw new Error("Razorpay checkout could not be initialized.");
        if (!cancelled) setReady(true);
      })
      .catch((caught: unknown) => {
        if (!cancelled) setError(caught instanceof Error ? caught.message : "Unable to prepare checkout.");
      });
    return () => {
      cancelled = true;
    };
  }, []);

  async function verify(response: RazorpaySuccess) {
    setVerifying(true);
    setError(null);
    try {
      const result = await paymentsApi.verifyPayment(checkout.booking_id, response);
      posthog.capture("payment_completed", { provider: checkout.provider, amount: checkout.amount, currency: checkout.currency });
      if (result.status === "confirmed") {
        onConfirmedRef.current();
        return;
      }
      setMessage("Payment received. Your booking will be confirmed in a moment.");
    } catch (caught) {
      // The payment webhook remains the source of truth (and refunds payments for taken slots).
      setMessage(getErrorMessage(caught));
    } finally {
      setVerifying(false);
    }
  }

  function startPayment() {
    if (!window.Razorpay) return;
    posthog.capture("payment_checkout_started", { provider: checkout.provider, checkout_type: "embedded" });
    setError(null);
    const razorpay = new window.Razorpay({
      key: checkout.key_id,
      amount: checkout.amount,
      currency: checkout.currency,
      name: checkout.name,
      description: checkout.description,
      order_id: checkout.order_id,
      prefill: checkout.prefill,
      notes: { booking_id: checkout.booking_id },
      handler: (response) => void verify(response),
    });
    razorpay.on("payment.failed", (response) => {
      setError(response.error?.description ?? "The payment failed. Please try again.");
    });
    razorpay.open();
  }

  return (
    <div className="provider-checkout">
      <p className="form-section-label">Secure payment · Razorpay</p>
      {error && <StatusMessage>{error}</StatusMessage>}
      {message && <StatusMessage tone="notice"><Check size={14}/> {message}</StatusMessage>}
      {verifying && <p className="booking-processing"><LoaderCircle className="spin"/> Confirming your payment</p>}
      {!message && !verifying && <button className="save-button" type="button" disabled={!ready} onClick={startPayment}>{ready ? <ArrowRight size={16}/> : <LoaderCircle className="spin" size={16}/>} Pay securely</button>}
    </div>
  );
}
