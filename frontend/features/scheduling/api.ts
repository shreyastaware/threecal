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

export type DateOverride = {
  id: string;
  exception_date: string;
  is_available: boolean;
  start_time: string | null;
  end_time: string | null;
  note: string | null;
};

export type DateOverrideInput = Pick<DateOverride, "is_available" | "start_time" | "end_time" | "note">;

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
  listOverrides: (range: { start?: string; end?: string } = {}) => {
    const params = new URLSearchParams();
    if (range.start) params.set("start", range.start);
    if (range.end) params.set("end", range.end);
    const query = params.toString();
    return apiRequest<DateOverride[]>(`/availability/overrides${query ? `?${query}` : ""}`);
  },
  setOverride: (date: string, input: DateOverrideInput) =>
    apiRequest<DateOverride>(`/availability/overrides/${date}`, { method: "PUT", body: JSON.stringify(input) }),
  deleteOverride: (date: string) =>
    apiRequest<void>(`/availability/overrides/${date}`, { method: "DELETE" }),
};
