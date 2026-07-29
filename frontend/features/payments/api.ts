import { apiRequest } from "@/lib/api/client";

export type PaymentProvider =
  | "stripe"
  | "razorpay"
  | "cashfree"
  | "paypal"
  | "btcpay";

export type Checkout = {
  provider: PaymentProvider;
  provider_payment_id: string;
  client_secret: string | null;
  checkout_url: string | null;
  public_key: string | null;
};

export const paymentsApi = {
  createCheckout: (bookingId: string) =>
    apiRequest<Checkout>(`/payments/bookings/${bookingId}/checkout`, {
      method: "POST",
    }),
};
