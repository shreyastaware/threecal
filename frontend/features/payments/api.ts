import { apiRequest } from "@/lib/api/client";

export const PAYMENT_PROVIDERS = [
  "stripe",
  "razorpay",
  "cashfree",
  "paypal",
  "btcpay",
] as const;

export type PaymentProvider = (typeof PAYMENT_PROVIDERS)[number];

export type PaymentConfig = {
  provider: PaymentProvider;
  account_id: string | null;
  connected: boolean;
};

export type CredentialConnectInput = {
  provider: PaymentProvider;
  api_key: string;
  secret_key?: string;
  account_id?: string;
  store_url?: string;
  store_id?: string;
  webhook_secret?: string;
};

export type Checkout = {
  provider: PaymentProvider;
  provider_payment_id: string;
  client_secret: string | null;
  checkout_url: string | null;
};

export const paymentsApi = {
  getConfig: () => apiRequest<PaymentConfig | null>("/payments/config"),
  connectCredentials: (input: CredentialConnectInput) =>
    apiRequest<PaymentConfig>("/payments/config", {
      method: "POST",
      body: JSON.stringify(input),
    }),
  startOAuth: (provider: "stripe" | "paypal") =>
    apiRequest<{ authorization_url: string }>(
      `/payments/oauth/${provider}/authorize`,
    ),
  createCheckout: (bookingId: string) =>
    apiRequest<Checkout>(`/payments/bookings/${bookingId}/checkout`, {
      method: "POST",
    }),
};
