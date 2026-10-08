"use client";

import { useQuery } from "@tanstack/react-query";

import { useAuth } from "@/features/auth/hooks/use-auth";
import { paymentsApi } from "@/features/payments/api";

export const PAYMENT_ACCOUNT_KEY = ["payments", "account"] as const;

export function usePaymentAccount() {
  const { user } = useAuth();
  return useQuery({
    queryKey: PAYMENT_ACCOUNT_KEY,
    queryFn: paymentsApi.getAccount,
    enabled: Boolean(user),
  });
}
