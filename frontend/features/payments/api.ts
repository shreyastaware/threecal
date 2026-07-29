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

export type BusinessType =
  | "llp"
  | "ngo"
  | "other"
  | "individual"
  | "partnership"
  | "proprietorship"
  | "public_limited"
  | "private_limited"
  | "trust"
  | "society"
  | "not_yet_registered"
  | "educational_institutes";

export type PaymentAccount = {
  account_name: string;
  account_email: string;
  business_type: BusinessType;
  business_name: string;
  branch_ifsc_code: string;
  masked_account_number: string;
  beneficiary_name: string;
};

export type PaymentAccountCreate = Omit<
  PaymentAccount,
  "masked_account_number"
> & {
  account_number: string;
};

export type PaymentAccountUpdate = Omit<
  PaymentAccountCreate,
  "account_number"
> & {
  account_number?: string;
};

export const paymentsApi = {
  getAccount: () => apiRequest<PaymentAccount | null>("/payments/account"),
  createAccount: (input: PaymentAccountCreate) =>
    apiRequest<PaymentAccount>("/payments/account", {
      method: "POST",
      body: JSON.stringify(input),
    }),
  updateAccount: (input: PaymentAccountUpdate) =>
    apiRequest<PaymentAccount>("/payments/account", {
      method: "PATCH",
      body: JSON.stringify(input),
    }),
  createCheckout: (bookingId: string) =>
    apiRequest<Checkout>(`/payments/bookings/${bookingId}/checkout`, {
      method: "POST",
    }),
};
