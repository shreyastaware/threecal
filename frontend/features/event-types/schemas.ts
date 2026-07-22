import { z } from "zod";

export const eventTypeSchema = z.object({
  title: z.string().trim().min(2, "Title must be at least 2 characters").max(120),
  slug: z
    .string()
    .trim()
    .toLowerCase()
    .min(2, "Slug must be at least 2 characters")
    .max(80)
    .regex(/^[a-z0-9-]+$/, "Use lowercase letters, numbers, and hyphens"),
  description: z.string().max(2000).optional(),
  duration_minutes: z.number().int().min(5).max(480),
  slot_interval_minutes: z.number().int().min(5).max(480),
  price_minor: z.number().int().min(0),
  currency: z.string().trim().toUpperCase().length(3, "Use a 3-letter currency"),
  is_active: z.boolean(),
});

export type EventTypeFormValues = z.infer<typeof eventTypeSchema>;
