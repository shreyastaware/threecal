import { z } from "zod";

export const businessTypeOptions = [
  { value: "llp", label: "LLP" },
  { value: "ngo", label: "NGO" },
  { value: "other", label: "Other" },
  { value: "individual", label: "Individual" },
  { value: "partnership", label: "Partnership" },
  { value: "proprietorship", label: "Proprietorship" },
  { value: "public_limited", label: "Public limited" },
  { value: "private_limited", label: "Private limited" },
  { value: "trust", label: "Trust" },
  { value: "society", label: "Society" },
  { value: "not_yet_registered", label: "Not yet registered" },
  { value: "educational_institutes", label: "Educational institutes" },
] as const;

const accountNumberSchema = z
  .string()
  .regex(/^\d{6,34}$/, "Account number must contain 6 to 34 digits");

export const paymentAccountFormSchema = z.object({
  account_name: z
    .string()
    .trim()
    .min(2, "Enter the account name")
    .max(120),
  account_email: z
    .string()
    .trim()
    .email("Enter a valid account email")
    .max(320),
  business_type: z.enum([
    "llp",
    "ngo",
    "other",
    "individual",
    "partnership",
    "proprietorship",
    "public_limited",
    "private_limited",
    "trust",
    "society",
    "not_yet_registered",
    "educational_institutes",
  ]),
  business_name: z
    .string()
    .trim()
    .min(2, "Enter the business name")
    .max(160),
  branch_ifsc_code: z
    .string()
    .trim()
    .regex(
      /^[A-Za-z]{4}0[A-Za-z0-9]{6}$/,
      "Enter a valid 11-character IFSC code",
    ),
  account_number: z.union([z.literal(""), accountNumberSchema]),
  beneficiary_name: z
    .string()
    .trim()
    .min(2, "Enter the beneficiary name")
    .max(120),
});

export type PaymentAccountFormValues = z.infer<
  typeof paymentAccountFormSchema
>;
