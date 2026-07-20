import { apiRequest } from "@/lib/api/client";

import type {
  AuthResponse,
  LoginInput,
  RegisterInput,
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
};
