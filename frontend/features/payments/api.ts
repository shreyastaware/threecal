import { apiRequest } from "@/lib/api/client";

// Invitees pay into the platform account; Razorpay Route transfers the host share.
export type PaymentProvider = "razorpay";

export type Checkout = {
  provider: PaymentProvider;
  booking_id: string;
  key_id: string;
  order_id: string;
  amount: number;
  currency: string;
  name: string;
  description: string;
  prefill: { name: string; email: string };
};

export type PaymentVerificationInput = {
  razorpay_order_id: string;
  razorpay_payment_id: string;
  razorpay_signature: string;
};

export type PaymentVerification = {
  booking_id: string;
  status: "pending" | "confirmed" | "cancelled" | "expired";
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

export type LinkedAccountStatus =
  | "not_started"
  | "requested"
  | "needs_clarification"
  | "under_review"
  | "activated"
  | "suspended";

export type PayoutRequirement = {
  field_reference: string;
  reason_code: string;
  status: string;
  description: string | null;
};

export type PaymentAccount = {
  account_name: string;
  account_email: string;
  business_type: BusinessType;
  business_name: string;
  branch_ifsc_code: string;
  masked_account_number: string;
  beneficiary_name: string;
  // Nullable for accounts saved before payout onboarding existed.
  phone: string | null;
  business_category: string | null;
  business_subcategory: string | null;
  street1: string | null;
  street2: string | null;
  city: string | null;
  state: string | null;
  postal_code: string | null;
  masked_pan: string | null;
  activation_status: LinkedAccountStatus;
  payouts_enabled: boolean;
  payouts_configured: boolean;
  requirements: PayoutRequirement[];
};

type PaymentAccountDetails = {
  account_name: string;
  account_email: string;
  business_type: BusinessType;
  business_name: string;
  branch_ifsc_code: string;
  beneficiary_name: string;
  phone: string;
  business_category: string;
  business_subcategory: string;
  street1: string;
  street2: string | null;
  city: string;
  state: string;
  postal_code: string;
};

export type PaymentAccountCreate = PaymentAccountDetails & {
  account_number: string;
  pan: string;
};

export type PaymentAccountUpdate = PaymentAccountDetails & {
  // Omit to keep the saved value.
  account_number?: string;
  pan?: string;
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
  syncAccount: () =>
    apiRequest<PaymentAccount>("/payments/account/sync", { method: "POST" }),
  createCheckout: (bookingId: string) =>
    apiRequest<Checkout>(`/payments/bookings/${bookingId}/checkout`, {
      method: "POST",
    }),
  verifyPayment: (bookingId: string, input: PaymentVerificationInput) =>
    apiRequest<PaymentVerification>(`/payments/bookings/${bookingId}/verify`, {
      method: "POST",
      body: JSON.stringify(input),
    }),
};
