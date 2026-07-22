import { z } from "zod";

import { PAYMENT_PROVIDERS } from "./api";

export const credentialConnectSchema = z.object({
  provider: z.enum(PAYMENT_PROVIDERS),
  api_key: z.string().trim().min(1, "Enter the provider key"),
  secret_key: z.string().trim().optional(),
  account_id: z.string().trim().optional(),
  store_url: z.string().trim().optional(),
  store_id: z.string().trim().optional(),
  webhook_secret: z.string().trim().optional(),
}).superRefine((values, context) => {
  if (["razorpay", "cashfree"].includes(values.provider) && !values.secret_key) {
    context.addIssue({ code: "custom", path: ["secret_key"], message: "This provider requires both key fields" });
  }
  if (values.provider === "btcpay" && (!values.store_url || !values.store_id)) {
    context.addIssue({ code: "custom", path: ["store_url"], message: "BTCPay requires a store URL and store ID" });
  }
});

export type CredentialConnectFormValues = z.infer<typeof credentialConnectSchema>;
