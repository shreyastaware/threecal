"use client";

import { useMutation, useQuery } from "@tanstack/react-query";
import {
  ArrowUpRight,
  Check,
  ChevronDown,
  KeyRound,
  LoaderCircle,
  LockKeyhole,
  ShieldCheck,
} from "lucide-react";
import Image from "next/image";
import posthog from "posthog-js";
import { useState } from "react";

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
  const [selectedProvider, setSelectedProvider] = useState<
    OAuthPaymentProvider | ""
  >("");
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
  const connectedOAuthProvider = OAUTH_PAYMENT_PROVIDERS.find(
    (provider) => provider === connectedProvider,
  );
  const displayedProvider = connectedOAuthProvider ?? selectedProvider;
  const selectedValue = connectedProvider ?? selectedProvider;
  const providerSelectionLocked =
    config.isLoading || oauth.isPending || Boolean(connectedProvider);
  const displayedDetails = displayedProvider
    ? providerDetails[displayedProvider]
    : null;
  const displayedLogo = displayedProvider
    ? PAYMENT_PROVIDER_LOGOS[displayedProvider]
    : null;
  const isDisplayedProviderConnected =
    displayedProvider === connectedOAuthProvider;
  const isDisplayedProviderPending =
    oauth.isPending && oauth.variables === displayedProvider;

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
                ? "New paid bookings will use this account. Only one payment connection is allowed, so other providers are now locked."
                : "Connect one account before publishing paid event types."}
            </p>
          </div>
        </div>

        <div className="provider-picker">
          <label htmlFor="payment-provider">
            <span>Payment provider</span>
            <strong>
              {connectedProvider
                ? "Your provider is locked after connection"
                : "Select the account you want to connect"}
            </strong>
          </label>
          <div className="provider-select-shell">
            <select
              disabled={providerSelectionLocked}
              id="payment-provider"
              onChange={(event) =>
                setSelectedProvider(
                  event.target.value as OAuthPaymentProvider | "",
                )
              }
              value={selectedValue}
            >
              <option value="">Select a payment provider</option>
              {OAUTH_PAYMENT_PROVIDERS.map((provider) => (
                <option key={provider} value={provider}>
                  {providerLabels[provider]}
                </option>
              ))}
              {connectedProvider && !connectedOAuthProvider && (
                <option value={connectedProvider}>
                  {providerLabels[connectedProvider]}
                </option>
              )}
            </select>
            <span className="provider-select-icon" aria-hidden="true">
              {config.isLoading || oauth.isPending ? (
                <LoaderCircle className="spin" size={17} />
              ) : connectedProvider ? (
                <LockKeyhole size={17} />
              ) : (
                <ChevronDown size={17} />
              )}
            </span>
          </div>
          <p>
            {connectedProvider
              ? `${providerLabels[connectedProvider]} is the only provider connected to this account.`
              : "The provider details and connection action appear after you make a selection."}
          </p>
        </div>

        {displayedProvider && displayedDetails && displayedLogo && (
          <div className="provider-reveal" aria-live="polite">
            <article
              className={`provider-card provider-${displayedProvider} ${isDisplayedProviderConnected ? "is-connected is-locked" : ""}`}
            >
              <div className="provider-card-head">
                <span className="provider-logo" aria-hidden="true">
                  <Image
                    alt=""
                    height={displayedLogo.height}
                    src={displayedLogo.src}
                    width={displayedLogo.width}
                  />
                </span>
                <span className="provider-market">
                  {displayedDetails.market}
                </span>
              </div>
              <div className="provider-card-copy">
                <h3>{providerLabels[displayedProvider]}</h3>
                <p>{displayedDetails.description}</p>
              </div>
              {isDisplayedProviderConnected && (
                <span className="provider-connected-label">
                  <Check size={13} /> Connected · selection locked
                </span>
              )}
              {!connectedProvider && (
                <button
                  className="provider-connect-button"
                  disabled={oauth.isPending}
                  onClick={() => beginOAuth(displayedProvider)}
                  type="button"
                >
                  {isDisplayedProviderPending ? (
                    <LoaderCircle className="spin" size={15} />
                  ) : (
                    <ArrowUpRight size={15} />
                  )}
                  {isDisplayedProviderPending
                    ? "Opening provider"
                    : `Connect ${providerLabels[displayedProvider]}`}
                </button>
              )}
              {oauth.isError && oauth.variables === displayedProvider && (
                <StatusMessage>{getErrorMessage(oauth.error)}</StatusMessage>
              )}
            </article>
          </div>
        )}

        {config.isError && (
          <StatusMessage>{getErrorMessage(config.error)}</StatusMessage>
        )}

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
