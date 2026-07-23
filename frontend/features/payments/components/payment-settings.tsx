"use client";

import { zodResolver } from "@hookform/resolvers/zod";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Check, ExternalLink, LoaderCircle, ShieldCheck } from "lucide-react";
import posthog from "posthog-js";
import { useState } from "react";
import { useForm } from "react-hook-form";

import { StatusMessage } from "@/features/dashboard/components/status-message";
import { paymentsApi, PAYMENT_PROVIDERS, type PaymentProvider } from "@/features/payments/api";
import { credentialConnectSchema, type CredentialConnectFormValues } from "@/features/payments/schemas";
import { getErrorMessage } from "@/lib/api/client";

const providerLabels: Record<PaymentProvider, string> = {
  stripe: "Stripe",
  razorpay: "Razorpay",
  cashfree: "Cashfree",
  paypal: "PayPal",
  btcpay: "BTCPay",
};

export function PaymentSettings() {
  const queryClient = useQueryClient();
  const config = useQuery({ queryKey: ["payments", "config"], queryFn: paymentsApi.getConfig });
  const [provider, setProvider] = useState<PaymentProvider>("cashfree");
  const emptyValues: CredentialConnectFormValues = { provider: "cashfree", api_key: "", secret_key: "", account_id: "", store_url: "", store_id: "", webhook_secret: "" };
  const { register, reset, handleSubmit, formState: { errors } } = useForm<CredentialConnectFormValues>({ resolver: zodResolver(credentialConnectSchema), defaultValues: emptyValues });
  const connect = useMutation({
    mutationFn: paymentsApi.connectCredentials,
    onSuccess: (saved) => {
      queryClient.setQueryData(["payments", "config"], saved);
      posthog.capture("payment_provider_connected", {
        provider: saved.provider,
        connection_method: "credentials",
      });
      reset({ ...emptyValues, provider: saved.provider });
      setProvider(saved.provider);
    },
  });
  const oauth = useMutation({ mutationFn: paymentsApi.startOAuth });

  async function beginOAuth(oauthProvider: "stripe" | "paypal") {
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

  const onSubmit = handleSubmit((values) => connect.mutate({ ...values, provider }));
  const isCredentialProvider = provider !== "stripe" && provider !== "paypal";

  return (
    <section className="workspace-panel payment-panel">
      <div className="panel-heading">
        <div><span>Payment routing</span><h2>Collect on your terms</h2></div>
        <p>Payments go directly through the provider connected to your account. Secrets are encrypted by the API and never returned here.</p>
      </div>
      <div className="payment-settings-body">
        <div className="connected-provider">
          <ShieldCheck size={18}/>
          <div><strong>{config.data?.connected ? `${providerLabels[config.data.provider]} connected` : "No payment provider connected"}</strong><p>{config.data?.connected ? "Paid event types can route payments through this account once platform billing is ready." : "Connect a provider before publishing paid event types."}</p></div>
        </div>
        <div className="provider-tabs" role="tablist" aria-label="Payment providers">
          {PAYMENT_PROVIDERS.map((item) => <button className={provider === item ? "active" : ""} key={item} type="button" onClick={() => setProvider(item)}>{providerLabels[item]}</button>)}
        </div>
        {(provider === "stripe" || provider === "paypal") ? <div className="oauth-connect">
          <p>{providerLabels[provider]} uses a secure OAuth connection. You will be redirected to the provider and returned to this dashboard.</p>
          {oauth.isError && <StatusMessage>{getErrorMessage(oauth.error)}</StatusMessage>}
          <button className="save-button" type="button" disabled={oauth.isPending} onClick={() => beginOAuth(provider)}>{oauth.isPending ? <LoaderCircle className="spin" size={16}/> : <ExternalLink size={16}/>} Connect {providerLabels[provider]}</button>
        </div> : <form className="credential-form" onSubmit={onSubmit} noValidate>
          <input type="hidden" value={provider} {...register("provider")} />
          <label><span>{providerLabels[provider]} API key</span><input type="password" autoComplete="new-password" {...register("api_key")} />{errors.api_key && <small className="field-error">{errors.api_key.message}</small>}</label>
          <label><span>Secret key</span><input type="password" autoComplete="new-password" {...register("secret_key")} />{errors.secret_key && <small className="field-error">{errors.secret_key.message}</small>}</label>
          {provider === "btcpay" && <><label><span>Store URL</span><input placeholder="https://store.example.com" {...register("store_url")} />{errors.store_url && <small className="field-error">{errors.store_url.message}</small>}</label><label><span>Store ID</span><input {...register("store_id")} />{errors.store_id && <small className="field-error">{errors.store_id.message}</small>}</label></>}
          {provider !== "btcpay" && <label><span>Account or merchant ID <small>(optional)</small></span><input {...register("account_id")} /></label>}
          <label><span>Webhook secret <small>(optional)</small></span><input type="password" autoComplete="new-password" {...register("webhook_secret")} /></label>
          {connect.isError && <StatusMessage>{getErrorMessage(connect.error)}</StatusMessage>}
          {connect.isSuccess && <StatusMessage tone="success"><Check size={14}/> Provider connected.</StatusMessage>}
          <button className="save-button" type="submit" disabled={connect.isPending}>{connect.isPending ? <LoaderCircle className="spin" size={16}/> : <Check size={16}/>} {connect.isPending ? "Connecting" : "Save provider"}</button>
        </form>}
        {isCredentialProvider && <p className="form-hint">The API registers a webhook during connection. Provider verification may take a moment.</p>}
      </div>
    </section>
  );
}
