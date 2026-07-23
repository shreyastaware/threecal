"use client";

import { useMutation, useQuery } from "@tanstack/react-query";
import {
  ArrowUpRight,
  Check,
  KeyRound,
  LoaderCircle,
  LockKeyhole,
  RefreshCw,
  ShieldCheck,
} from "lucide-react";
import Image from "next/image";
import posthog from "posthog-js";

import { StatusMessage } from "@/features/dashboard/components/status-message";
import {
  OAUTH_PAYMENT_PROVIDERS,
  paymentsApi,
  type OAuthPaymentProvider,
  type PaymentProvider,
} from "@/features/payments/api";
import { PAYMENT_PROVIDER_LOGOS } from "@/features/payments/provider-assets";
import { getErrorMessage } from "@/lib/api/client";

const providerLabels: Record<PaymentProvider, string> = {
  stripe: "Stripe",
  razorpay: "Razorpay",
  cashfree: "Cashfree",
  paypal: "PayPal",
  btcpay: "BTCPay",
};

const providerDetails: Record<
  OAuthPaymentProvider,
  {
    description: string;
    market: string;
  }
> = {
  stripe: {
    description: "Cards, wallets, and international payments",
    market: "Global",
  },
  paypal: {
    description: "PayPal balance, cards, and pay-later options",
    market: "Global",
  },
  razorpay: {
    description: "UPI, cards, net banking, and wallets",
    market: "India",
  },
  cashfree: {
    description: "UPI, cards, and bank transfer checkout",
    market: "India",
  },
};

export function PaymentSettings() {
  const config = useQuery({
    queryKey: ["payments", "config"],
    queryFn: paymentsApi.getConfig,
    refetchOnWindowFocus: true,
  });
  const oauth = useMutation({ mutationFn: paymentsApi.startOAuth });

  async function beginOAuth(oauthProvider: OAuthPaymentProvider) {
    try {
      const { authorization_url } = await oauth.mutateAsync(oauthProvider);
      posthog.capture("payment_provider_oauth_started", {
        provider: oauthProvider,
      });
      window.location.assign(authorization_url);
    } catch {
      // The mutation error is rendered below.
    }
  }

  const connectedProvider = config.data?.connected
    ? config.data.provider
    : null;

  return (
    <section className="workspace-panel payment-panel">
      <div className="panel-heading">
        <div>
          <span>Payment routing</span>
          <h2>Bring your own account</h2>
        </div>
        <p>
          Choose a provider and approve Threecal on its website. Your account
          credentials never enter this dashboard.
        </p>
      </div>

      <div className="payment-settings-body">
        <div
          className={`connected-provider ${connectedProvider ? "is-connected" : ""}`}
        >
          {config.isLoading ? (
            <LoaderCircle className="spin" size={18} />
          ) : (
            <ShieldCheck size={18} />
          )}
          <div>
            <span>Active payout route</span>
            <strong>
              {connectedProvider
                ? `${providerLabels[connectedProvider]} is connected`
                : "No provider connected yet"}
            </strong>
            <p>
              {connectedProvider
                ? "New paid bookings will use this account. Connecting another provider replaces the active route."
                : "Connect one account before publishing paid event types."}
            </p>
          </div>
        </div>

        <div className="provider-grid" aria-label="Payment providers">
          {OAUTH_PAYMENT_PROVIDERS.map((provider) => {
            const details = providerDetails[provider];
            const logo = PAYMENT_PROVIDER_LOGOS[provider];
            const isConnected = connectedProvider === provider;
            const isPending =
              oauth.isPending && oauth.variables === provider;

            return (
              <article
                className={`provider-card provider-${provider} ${isConnected ? "is-connected" : ""}`}
                key={provider}
              >
                <div className="provider-card-head">
                  <span className="provider-logo" aria-hidden="true">
                    <Image
                      alt=""
                      height={logo.height}
                      src={logo.src}
                      width={logo.width}
                    />
                  </span>
                  <span className="provider-market">{details.market}</span>
                </div>
                <div className="provider-card-copy">
                  <h3>{providerLabels[provider]}</h3>
                  <p>{details.description}</p>
                </div>
                {isConnected && (
                  <span className="provider-connected-label">
                    <Check size={13} /> Connected
                  </span>
                )}
                <button
                  className="provider-connect-button"
                  disabled={oauth.isPending}
                  onClick={() => beginOAuth(provider)}
                  type="button"
                >
                  {isPending ? (
                    <LoaderCircle className="spin" size={15} />
                  ) : isConnected ? (
                    <RefreshCw size={15} />
                  ) : (
                    <ArrowUpRight size={15} />
                  )}
                  {isPending
                    ? "Opening provider"
                    : isConnected
                      ? "Reconnect"
                      : `Connect ${providerLabels[provider]}`}
                </button>
                {oauth.isError && oauth.variables === provider && (
                  <StatusMessage>{getErrorMessage(oauth.error)}</StatusMessage>
                )}
              </article>
            );
          })}
        </div>

        <div className="oauth-security-note">
          <LockKeyhole size={18} />
          <div>
            <strong>Protected by provider-hosted OAuth</strong>
            <p>
              You sign in and approve access on the provider&apos;s website.
              Threecal receives a limited token through its backend and never
              asks for your API keys, client secrets, or password.
            </p>
          </div>
          <KeyRound size={18} />
        </div>
      </div>
    </section>
  );
}
