import { apiRequest } from "@/lib/api/client";
import type { User } from "@/features/auth/types/auth";

export type WorkingHour = {
  id?: string;
  weekday: number;
  start_time: string;
  end_time: string;
  is_enabled: boolean;
  breaks: { start_time: string; end_time: string }[];
};

export const schedulingApi = {
  updateProfile: (data: Partial<Pick<User, "full_name" | "username" | "bio" | "timezone" | "avatar_url">>) =>
    apiRequest<User>("/users/me", { method: "PATCH", body: JSON.stringify(data) }),
  getSchedule: () => apiRequest<WorkingHour[]>("/availability"),
  saveSchedule: (working_hours: WorkingHour[]) =>
    apiRequest<WorkingHour[]>("/availability", { method: "PUT", body: JSON.stringify({ working_hours }) }),
};
