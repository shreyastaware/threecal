"use client";

import { useQuery, useQueryClient } from "@tanstack/react-query";
import { createContext, useCallback, useMemo } from "react";

import { authApi } from "@/features/auth/api";
import type {
  LoginInput,
  RegisterInput,
  User,
} from "@/features/auth/types/auth";

type AuthContextValue = {
  user: User | null;
  isLoading: boolean;
  login: (input: LoginInput) => Promise<User>;
  register: (input: RegisterInput) => Promise<User>;
  logout: () => Promise<void>;
};

export const AuthContext = createContext<AuthContextValue | null>(null);

const CURRENT_USER_KEY = ["auth", "current-user"] as const;

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const queryClient = useQueryClient();
  const currentUserQuery = useQuery({
    queryKey: CURRENT_USER_KEY,
    queryFn: authApi.currentUser,
    retry: false,
  });

  const login = useCallback(
    async (input: LoginInput) => {
      const { user } = await authApi.login(input);
      queryClient.setQueryData(CURRENT_USER_KEY, user);
      return user;
    },
    [queryClient],
  );

  const register = useCallback(
    async (input: RegisterInput) => {
      const { user } = await authApi.register(input);
      queryClient.setQueryData(CURRENT_USER_KEY, user);
      return user;
    },
    [queryClient],
  );

  const logout = useCallback(async () => {
    await authApi.logout();
    queryClient.setQueryData(CURRENT_USER_KEY, null);
  }, [queryClient]);

  const value = useMemo(
    () => ({
      user: currentUserQuery.data ?? null,
      isLoading: currentUserQuery.isLoading,
      login,
      register,
      logout,
    }),
    [currentUserQuery.data, currentUserQuery.isLoading, login, logout, register],
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}
