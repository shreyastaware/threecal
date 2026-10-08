import { z } from "zod";

import type { LinkedAccountStatus } from "@/features/payments/api";

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

// Mirrors backend/app/domains/payments/categories.py (Razorpay Route categories).
export const businessCategoryOptions = [
  {
    value: "healthcare",
    label: "Healthcare",
    subcategories: [
      { value: "clinic", label: "Clinic" },
      { value: "doctors", label: "Doctors" },
      { value: "health_practitioners_medical_services", label: "Health practitioners" },
      { value: "dentists_and_orthodontists", label: "Dentists and orthodontists" },
      { value: "ophthalmologists", label: "Ophthalmologists" },
      { value: "osteopaths", label: "Osteopaths" },
      { value: "dietician", label: "Dietician" },
      { value: "fitness", label: "Fitness" },
      { value: "health_coaching", label: "Health coaching" },
      { value: "lab", label: "Lab" },
    ],
  },
  {
    value: "education",
    label: "Education",
    subcategories: [
      { value: "coaching", label: "Coaching" },
      { value: "professional_courses", label: "Professional courses" },
      { value: "elearning", label: "E-learning" },
      { value: "distance_learning", label: "Distance learning" },
    ],
  },
  {
    value: "services",
    label: "Services",
    subcategories: [
      { value: "consulting", label: "Consulting" },
      { value: "professional_services", label: "Professional services" },
      { value: "business_services", label: "Business services" },
      { value: "legal", label: "Legal" },
      { value: "debt_marriage_personal_counseling_service", label: "Counselling" },
      { value: "event_planning", label: "Event planning" },
      { value: "interior_design_and_architect", label: "Interior design and architecture" },
      { value: "photographic_studio", label: "Photography" },
      { value: "ad_and_marketing", label: "Advertising and marketing" },
    ],
  },
  {
    value: "it_and_software",
    label: "IT and software",
    subcategories: [
      { value: "consulting_and_outsourcing", label: "Consulting and outsourcing" },
      { value: "web_development", label: "Web development" },
      { value: "technical_support", label: "Technical support" },
      { value: "saas", label: "SaaS" },
    ],
  },
] as const;

export function subcategoriesFor(category: string) {
  return (
    businessCategoryOptions.find((option) => option.value === category)
      ?.subcategories ?? []
  );
}

export const activationStatusLabels: Record<LinkedAccountStatus, string> = {
  not_started: "Not submitted",
  requested: "Submitted",
  needs_clarification: "Action needed",
  under_review: "Under review",
  activated: "Payouts active",
  suspended: "Suspended",
};

// Business types where Razorpay expects the owner's personal PAN.
export const personalPanBusinessTypes = new Set([
  "individual",
  "not_yet_registered",
  "proprietorship",
]);

export function normalizePhone(value: string): string {
  return value.replace(/[\s()+-]/g, "");
}

const accountNumberSchema = z
  .string()
  .regex(/^\d{6,34}$/, "Account number must contain 6 to 34 digits");

const panSchema = z
  .string()
  .trim()
  .regex(/^[A-Za-z]{5}\d{4}[A-Za-z]$/, "PAN must look like ABCDE1234F");

export const paymentAccountFormSchema = z
  .object({
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
    phone: z
      .string()
      .trim()
      .refine(
        (value) => /^\d{8,15}$/.test(normalizePhone(value)),
        "Enter a valid phone number",
      ),
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
      .min(4, "Enter the legal business name (at least 4 characters)")
      .max(160),
    business_category: z.string().min(1, "Choose a business category"),
    business_subcategory: z.string().min(1, "Choose a sub-category"),
    pan: z.union([z.literal(""), panSchema]),
    street1: z.string().trim().min(3, "Enter the street address").max(100),
    street2: z.string().trim().max(100),
    city: z.string().trim().min(2, "Enter the city").max(100),
    state: z.string().trim().min(2, "Enter the state").max(32),
    postal_code: z
      .string()
      .trim()
      .regex(/^[1-9]\d{5}$/, "Enter a 6-digit PIN code"),
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
  })
  .superRefine((values, context) => {
    const subcategories = subcategoriesFor(values.business_category);
    if (
      values.business_subcategory &&
      !subcategories.some((option) => option.value === values.business_subcategory)
    ) {
      context.addIssue({
        code: "custom",
        message: "Choose a sub-category for this category",
        path: ["business_subcategory"],
      });
    }
    if (values.pan) {
      const holder = values.pan.toUpperCase()[3];
      const personal = personalPanBusinessTypes.has(values.business_type);
      if (personal && holder !== "P") {
        context.addIssue({
          code: "custom",
          message: "Enter the owner's personal PAN (4th character P)",
          path: ["pan"],
        });
      }
      if (!personal && !"CHFATBJGL".includes(holder)) {
        context.addIssue({
          code: "custom",
          message: "Enter the business PAN for this business type",
          path: ["pan"],
        });
      }
    }
  });

export type PaymentAccountFormValues = z.infer<
  typeof paymentAccountFormSchema
>;
