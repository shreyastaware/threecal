"use client";

import { useQuery, useQueryClient } from "@tanstack/react-query";
import { createContext, useCallback, useEffect, useMemo, useRef } from "react";
import posthog from "posthog-js";

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

export const CURRENT_USER_KEY = ["auth", "current-user"] as const;

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const queryClient = useQueryClient();
  const identifiedUserId = useRef<string | null>(null);
  const currentUserQuery = useQuery({
    queryKey: CURRENT_USER_KEY,
    queryFn: authApi.currentUser,
    retry: false,
  });

  const identifyUser = useCallback((user: User) => {
    if (identifiedUserId.current === user.id) return;

    if (identifiedUserId.current) {
      posthog.reset();
    }

    posthog.identify(user.id, {
      email: user.email,
      name: user.full_name,
    });
    identifiedUserId.current = user.id;
  }, []);

  useEffect(() => {
    if (currentUserQuery.data) {
      identifyUser(currentUserQuery.data);
    }
  }, [currentUserQuery.data, identifyUser]);

  const login = useCallback(
    async (input: LoginInput) => {
      const { user } = await authApi.login(input);
      identifyUser(user);
      queryClient.setQueryData(CURRENT_USER_KEY, user);
      return user;
    },
    [identifyUser, queryClient],
  );

  const register = useCallback(
    async (input: RegisterInput) => {
      const { user } = await authApi.register(input);
      identifyUser(user);
      queryClient.setQueryData(CURRENT_USER_KEY, user);
      return user;
    },
    [identifyUser, queryClient],
  );

  const logout = useCallback(async () => {
    await authApi.logout();
    posthog.reset();
    identifiedUserId.current = null;
    queryClient.setQueryData(CURRENT_USER_KEY, null);
    queryClient.removeQueries({ queryKey: ["availability"] });
    queryClient.removeQueries({ queryKey: ["event-types"] });
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
