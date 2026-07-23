import { apiRequest } from "@/lib/api/client";

export const PAYMENT_PROVIDER_VALUES = [
  "stripe",
  "razorpay",
  "cashfree",
  "paypal",
  "btcpay",
] as const;

export const OAUTH_PAYMENT_PROVIDERS = [
  "stripe",
  "paypal",
  "razorpay",
  "cashfree",
] as const;

export type PaymentProvider = (typeof PAYMENT_PROVIDER_VALUES)[number];
export type OAuthPaymentProvider = (typeof OAUTH_PAYMENT_PROVIDERS)[number];

export type PaymentConfig = {
  provider: PaymentProvider;
  account_id: string | null;
  connected: boolean;
};

export type Checkout = {
  provider: PaymentProvider;
  provider_payment_id: string;
  client_secret: string | null;
  checkout_url: string | null;
  public_key: string | null;
};

export const paymentsApi = {
  getConfig: () => apiRequest<PaymentConfig | null>("/payments/config"),
  startOAuth: (provider: OAuthPaymentProvider) =>
    apiRequest<{ authorization_url: string }>(
      `/payments/oauth/${provider}/authorize`,
    ),
  createCheckout: (bookingId: string) =>
    apiRequest<Checkout>(`/payments/bookings/${bookingId}/checkout`, {
      method: "POST",
    }),
};
