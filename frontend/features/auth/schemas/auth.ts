import { z } from "zod";

// Mirrors the backend password policy (NewPassword in users/schemas.py).
export const passwordSchema = z
  .string()
  .min(8, "Password must be at least 8 characters")
  .max(128, "Password must be 128 characters or fewer");

export const loginSchema = z.object({
  email: z.string().trim().email("Enter a valid email address"),
  password: z.string().min(1, "Enter your password"),
});

export const registerSchema = loginSchema.extend({
  full_name: z
    .string()
    .trim()
    .min(2, "Name must be at least 2 characters")
    .max(120, "Name must be 120 characters or fewer"),
  password: passwordSchema,
});

export const forgotPasswordSchema = z.object({
  email: z.string().trim().email("Enter a valid email address"),
});

export const resetPasswordSchema = z
  .object({
    new_password: passwordSchema,
    confirm_password: z.string().min(1, "Confirm your new password"),
  })
  .refine((values) => values.new_password === values.confirm_password, {
    message: "Passwords do not match",
    path: ["confirm_password"],
  });

export const changePasswordSchema = z
  .object({
    current_password: z.string().min(1, "Enter your current password"),
    new_password: passwordSchema,
    confirm_password: z.string().min(1, "Confirm your new password"),
  })
  .refine((values) => values.new_password === values.confirm_password, {
    message: "Passwords do not match",
    path: ["confirm_password"],
  })
  .refine((values) => values.new_password !== values.current_password, {
    message: "Choose a password that differs from your current one",
    path: ["new_password"],
  });

export const deleteAccountSchema = z.object({
  password: z.string().min(1, "Enter your password to confirm"),
});

export type LoginFormValues = z.infer<typeof loginSchema>;
export type RegisterFormValues = z.infer<typeof registerSchema>;
export type ForgotPasswordFormValues = z.infer<typeof forgotPasswordSchema>;
export type ResetPasswordFormValues = z.infer<typeof resetPasswordSchema>;
export type ChangePasswordFormValues = z.infer<typeof changePasswordSchema>;
export type DeleteAccountFormValues = z.infer<typeof deleteAccountSchema>;
