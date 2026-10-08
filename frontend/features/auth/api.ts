import { apiRequest } from "@/lib/api/client";

import type {
  AuthResponse,
  ChangePasswordInput,
  DeleteAccountInput,
  LoginInput,
  RegisterInput,
  ResetPasswordInput,
  User,
} from "./types/auth";

export const authApi = {
  currentUser: () => apiRequest<User>("/users/me"),
  login: (input: LoginInput) =>
    apiRequest<AuthResponse>("/auth/login", {
      method: "POST",
      body: JSON.stringify(input),
    }),
  register: (input: RegisterInput) =>
    apiRequest<AuthResponse>("/auth/register", {
      method: "POST",
      body: JSON.stringify(input),
    }),
  logout: () => apiRequest<void>("/auth/logout", { method: "POST" }),
  verifyEmail: (token: string) =>
    apiRequest<User>("/auth/verify-email", {
      method: "POST",
      body: JSON.stringify({ token }),
    }),
  resendVerification: () =>
    apiRequest<void>("/auth/resend-verification", { method: "POST" }),
  forgotPassword: (email: string) =>
    apiRequest<void>("/auth/forgot-password", {
      method: "POST",
      body: JSON.stringify({ email }),
    }),
  resetPassword: (input: ResetPasswordInput) =>
    apiRequest<void>("/auth/reset-password", {
      method: "POST",
      body: JSON.stringify(input),
    }),
  changePassword: (input: ChangePasswordInput) =>
    apiRequest<User>("/users/me/password", {
      method: "POST",
      body: JSON.stringify(input),
    }),
  deleteAccount: (input: DeleteAccountInput) =>
    apiRequest<void>("/users/me", {
      method: "DELETE",
      body: JSON.stringify(input),
    }),
};
