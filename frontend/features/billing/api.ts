import { apiRequest } from "@/lib/api/client";

export type PlatformBilling = {
  dodopayments_customer_id: string | null;
  payment_method_id: string | null;
  current_cycle_start: string;
  current_cycle_earnings: number;
  ready: boolean;
};

export type BillingSetup = {
  checkout_url: string;
  customer_id: string;
};

export const billingApi = {
  get: () => apiRequest<PlatformBilling>("/billing/me"),
  startSetup: () => apiRequest<BillingSetup>("/billing/setup", { method: "POST" }),
  completeSetup: (input: { payment_method_id: string; subscription_id: string }) =>
    apiRequest<PlatformBilling>("/billing/setup/complete", {
      method: "POST",
      body: JSON.stringify(input),
    }),
};
