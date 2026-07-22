import { z } from "zod";

export const bookingSchema = z.object({
  invitee_name: z.string().trim().min(2, "Name must be at least 2 characters").max(120),
  invitee_email: z.string().trim().email("Enter a valid email address"),
  invitee_timezone: z.string().min(1, "Choose a timezone"),
  notes: z.string().max(2000, "Notes must be 2000 characters or fewer").optional(),
});

export type BookingFormValues = z.infer<typeof bookingSchema>;
