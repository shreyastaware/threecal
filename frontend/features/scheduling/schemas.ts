import { z } from "zod";

const timeSchema = z.string().regex(/^([01]\d|2[0-3]):[0-5]\d$/, "Use a valid time");
const MAX_PROFILE_IMAGE_BYTES = 5 * 1024 * 1024;
const PROFILE_IMAGE_TYPES = ["image/jpeg", "image/png", "image/webp"];

export const profileSchema = z.object({
  full_name: z.string().trim().min(2, "Name must be at least 2 characters").max(120),
  username: z
    .string()
    .trim()
    .toLowerCase()
    .refine((value) => value === "" || /^[a-z0-9_-]{3,50}$/.test(value), "Use 3-50 lowercase letters, numbers, hyphens, or underscores"),
  timezone: z.string().min(1, "Choose a timezone"),
  bio: z.string().max(1000, "Bio must be 1000 characters or fewer"),
  avatar_url: z.string().max(2048, "Image URL is too long"),
});

export const profileImageSchema = z
  .custom<File>(
    (value) => typeof File !== "undefined" && value instanceof File,
    "Choose an image to upload",
  )
  .refine(
    (file) => file.size <= MAX_PROFILE_IMAGE_BYTES,
    "Profile images must be 5 MB or smaller",
  )
  .refine(
    (file) => PROFILE_IMAGE_TYPES.includes(file.type),
    "Upload a JPEG, PNG, or WebP image",
  );

export const workingHourSchema = z.object({
  weekday: z.number().int().min(0).max(6),
  start_time: timeSchema,
  end_time: timeSchema,
  is_enabled: z.boolean(),
  breaks: z.array(z.object({ start_time: timeSchema, end_time: timeSchema })),
});

export const scheduleSchema = z.array(workingHourSchema).superRefine((hours, context) => {
  for (const [index, hour] of hours.entries()) {
    if (hour.start_time >= hour.end_time) {
      context.addIssue({
        code: "custom",
        path: [index, "end_time"],
        message: "End time must be after start time",
      });
    }
    for (const [breakIndex, pause] of hour.breaks.entries()) {
      if (pause.start_time >= pause.end_time) {
        context.addIssue({
          code: "custom",
          path: [index, "breaks", breakIndex, "end_time"],
          message: "Break end must be after break start",
        });
      }
    }
  }
});

export type ProfileFormValues = z.infer<typeof profileSchema>;
