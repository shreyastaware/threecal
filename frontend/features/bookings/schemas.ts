import { z } from "zod";

export const cancelBookingSchema = z.object({
  reason: z.string().trim().max(500, "Keep the reason under 500 characters"),
});

export type CancelBookingValues = z.infer<typeof cancelBookingSchema>;

export const rescheduleBookingSchema = z.object({
  starts_at: z.string().min(1, "Choose a new time"),
});

export type RescheduleBookingValues = z.infer<typeof rescheduleBookingSchema>;
