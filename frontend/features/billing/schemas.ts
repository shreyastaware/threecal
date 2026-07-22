import { z } from "zod";

export const billingCompleteSchema = z.object({
  payment_method_id: z.string().trim().min(1, "Enter the payment method ID"),
  subscription_id: z.string().trim().min(1, "Enter the subscription ID"),
});

export type BillingCompleteFormValues = z.infer<typeof billingCompleteSchema>;
