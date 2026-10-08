"use client";

import { useMutation, useQueryClient } from "@tanstack/react-query";

import { CURRENT_USER_KEY } from "@/components/providers/auth-provider";
import { authApi } from "@/features/auth/api";
import { ApiError } from "@/lib/api/client";

export function useResendVerification() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: authApi.resendVerification,
    onError: (error) => {
      // Verified in another tab: refresh the user so the banner disappears.
      if (error instanceof ApiError && error.code === "email_already_verified") {
        void queryClient.invalidateQueries({ queryKey: CURRENT_USER_KEY });
      }
    },
  });
}
