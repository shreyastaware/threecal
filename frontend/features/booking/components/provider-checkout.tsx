"use client";

import { ArrowRight, Check, ExternalLink, LoaderCircle } from "lucide-react";
import { useEffect, useRef, useState } from "react";

import type { Checkout } from "@/features/payments/api";
import { StatusMessage } from "@/features/dashboard/components/status-message";

type StripeElement = { mount: (element: HTMLElement) => void; destroy: () => void };
type StripeElements = {
  create: (type: "payment", options: { layout: "tabs" }) => StripeElement;
};
type StripeClient = {
  elements: (options: { clientSecret: string }) => StripeElements;
  confirmPayment: (options: { elements: StripeElements; confirmParams: { return_url: string } }) => Promise<{ error?: { message?: string } }>;
};
type CashfreeClient = { checkout: (options: { paymentSessionId: string; redirectTarget: "_self" }) => Promise<void> };
type RazorpayOptions = { key: string; order_id: string; handler: () => void; modal?: { ondismiss?: () => void } };
type RazorpayClient = { open: () => void };

declare global {
  interface Window {
    Stripe?: (key: string) => StripeClient | null;
    Cashfree?: (options: { mode: "sandbox" | "production" }) => CashfreeClient;
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

export function ProviderCheckout({ checkout }: { checkout: Checkout }) {
  const [error, setError] = useState<string | null>(null);
  const [message, setMessage] = useState<string | null>(null);
  const [ready, setReady] = useState(false);
  const stripeElement = useRef<StripeElement | null>(null);
  const stripeElements = useRef<StripeElements | null>(null);
  const stripeClient = useRef<StripeClient | null>(null);
  const stripeMount = useRef<HTMLDivElement>(null);

  useEffect(() => {
    let cancelled = false;
    async function prepare() {
      try {
        if (checkout.provider === "stripe" && checkout.client_secret) {
          const key = process.env.NEXT_PUBLIC_STRIPE_PUBLISHABLE_KEY;
          if (!key) throw new Error("Stripe checkout is not configured on this website.");
          await loadScript("https://js.stripe.com/v3/");
          const stripe = window.Stripe?.(key);
          if (!stripe) throw new Error("Stripe checkout could not be initialized.");
          if (!stripeMount.current || cancelled) return;
          const elements = stripe.elements({ clientSecret: checkout.client_secret });
          const paymentElement = elements.create("payment", { layout: "tabs" });
          paymentElement.mount(stripeMount.current);
          stripeClient.current = stripe;
          stripeElements.current = elements;
          stripeElement.current = paymentElement;
          setReady(true);
        } else if (checkout.provider === "cashfree" && checkout.client_secret) {
          await loadScript("https://sdk.cashfree.com/js/v3/cashfree.js");
          if (!window.Cashfree) throw new Error("Cashfree checkout could not be initialized.");
          if (!cancelled) setReady(true);
        } else if (checkout.provider === "razorpay") {
          await loadScript("https://checkout.razorpay.com/v1/checkout.js");
          if (!window.Razorpay) throw new Error("Razorpay checkout could not be initialized.");
          if (!cancelled) setReady(true);
        } else if (!cancelled) {
          setReady(Boolean(checkout.checkout_url));
        }
      } catch (caught) {
        if (!cancelled) setError(caught instanceof Error ? caught.message : "Unable to prepare checkout.");
      }
    }
    void prepare();
    return () => {
      cancelled = true;
      stripeElement.current?.destroy();
    };
  }, [checkout]);

  async function startPayment() {
    setError(null);
    try {
      if (checkout.checkout_url) {
        window.location.assign(checkout.checkout_url);
        return;
      }
      if (checkout.provider === "stripe" && stripeClient.current && stripeElements.current) {
        const result = await stripeClient.current.confirmPayment({ elements: stripeElements.current, confirmParams: { return_url: window.location.href } });
        if (result.error) throw new Error(result.error.message ?? "Stripe could not confirm this payment.");
        setMessage("Payment submitted. Your booking will be confirmed after the provider webhook is received.");
        return;
      }
      if (checkout.provider === "cashfree" && checkout.client_secret && window.Cashfree) {
        await window.Cashfree({ mode: process.env.NEXT_PUBLIC_CASHFREE_MODE === "production" ? "production" : "sandbox" }).checkout({ paymentSessionId: checkout.client_secret, redirectTarget: "_self" });
        return;
      }
      if (checkout.provider === "razorpay" && window.Razorpay) {
        const key = process.env.NEXT_PUBLIC_RAZORPAY_KEY_ID;
        if (!key) throw new Error("Razorpay checkout is not configured on this website.");
        new window.Razorpay({ key, order_id: checkout.provider_payment_id, handler: () => setMessage("Payment submitted. Your booking will be confirmed after verification.") }).open();
        return;
      }
      throw new Error("This payment provider is not configured for browser checkout.");
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Unable to start payment.");
    }
  }

  return (
    <div className="provider-checkout">
      <p className="form-section-label">Secure payment · {checkout.provider}</p>
      {checkout.provider === "stripe" && checkout.client_secret && <div className="stripe-element" ref={stripeMount} />}
      {error && <StatusMessage>{error}</StatusMessage>}
      {message && <StatusMessage tone="success"><Check size={14}/> {message}</StatusMessage>}
      {!message && <button className="save-button" type="button" disabled={!ready} onClick={startPayment}>{!ready ? <LoaderCircle className="spin" size={16}/> : checkout.checkout_url ? <ExternalLink size={16}/> : <ArrowRight size={16}/>} {checkout.checkout_url ? "Continue to payment" : "Pay securely"}</button>}
    </div>
  );
}
