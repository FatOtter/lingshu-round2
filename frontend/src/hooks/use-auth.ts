"use client";

import { useCallback, useEffect } from "react";
import { useRouter } from "next/navigation";
import { useAuthStore } from "@/stores/auth-store";
import { settingApi } from "@/lib/api/setting";

const REFRESH_INTERVAL_MS = 4 * 60 * 1000; // 4 minutes

export function useAuth() {
  const router = useRouter();
  const { user, isAuthenticated, isLoading, setUser, setLoading, logout: clearAuth } = useAuthStore();

  const checkAuth = useCallback(async () => {
    try {
      const response = await settingApi.me();
      setUser(response.data);
    } catch {
      setUser(null);
    }
  }, [setUser]);

  const login = useCallback(
    async (email: string, password: string) => {
      const response = await settingApi.login(email, password);
      setUser(response.data.user);
      router.push("/");
    },
    [setUser, router],
  );

  const logout = useCallback(async () => {
    try {
      await settingApi.logout();
    } catch {
      // Ignore logout errors
    }
    clearAuth();
    router.push("/login");
  }, [clearAuth, router]);

  // Check auth on mount
  useEffect(() => {
    checkAuth();
  }, [checkAuth]);

  // Auto-refresh token
  useEffect(() => {
    if (!isAuthenticated) return;

    const interval = setInterval(async () => {
      try {
        await settingApi.refresh();
      } catch {
        clearAuth();
        router.push("/login");
      }
    }, REFRESH_INTERVAL_MS);

    return () => clearInterval(interval);
  }, [isAuthenticated, clearAuth, router]);

  return { user, isAuthenticated, isLoading, login, logout, setLoading };
}
