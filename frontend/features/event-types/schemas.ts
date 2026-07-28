import { z } from "zod";

export const eventTypeSchema = z
  .object({
    title: z.string().trim().min(2, "Title must be at least 2 characters").max(120),
    description: z.string().max(2000).optional(),
    duration_option: z.enum(["15", "30", "45", "60", "custom"]),
    custom_duration_minutes: z
      .number()
      .int("Enter a whole number")
      .min(5)
      .max(480)
      .optional(),
    slot_interval_minutes: z.number().int().min(5).max(480),
    price: z.number().int("Enter a whole number").min(0),
    is_active: z.boolean(),
    is_default: z.boolean(),
  })
  .superRefine((eventType, context) => {
    if (
      eventType.duration_option === "custom"
      && eventType.custom_duration_minutes === undefined
    ) {
      context.addIssue({
        code: "custom",
        message: "Enter a custom duration",
        path: ["custom_duration_minutes"],
      });
    }
  })
  .refine((eventType) => !eventType.is_default || eventType.is_active, {
    message: "A default booking must be visible on your booking page",
    path: ["is_default"],
  });

export type EventTypeFormValues = z.infer<typeof eventTypeSchema>;
