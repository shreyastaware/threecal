import { apiRequest } from "@/lib/api/client";
import type { User } from "@/features/auth/types/auth";

export type WorkingHour = {
  id?: string;
  weekday: number;
  start_time: string;
  end_time: string;
  is_enabled: boolean;
  breaks: { id?: string; start_time: string; end_time: string }[];
};

export type ProfileUpdate = Partial<Pick<User, "full_name" | "username" | "bio" | "timezone" | "avatar_url">>;

export const schedulingApi = {
  updateProfile: (data: ProfileUpdate) =>
    apiRequest<User>("/users/me", { method: "PATCH", body: JSON.stringify(data) }),
  uploadAvatar: (avatar: File) => {
    const formData = new FormData();
    formData.append("avatar", avatar);
    return apiRequest<User>("/users/me/avatar", {
      method: "POST",
      body: formData,
    });
  },
  getSchedule: () => apiRequest<WorkingHour[]>("/availability"),
  saveSchedule: (working_hours: WorkingHour[]) =>
    apiRequest<WorkingHour[]>("/availability", { method: "PUT", body: JSON.stringify({ working_hours }) }),
};
