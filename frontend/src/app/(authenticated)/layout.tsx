"use client";

import { useEffect } from "react";
import { useRouter } from "next/navigation";
import { Dock } from "@/components/layout/dock";
import { Header } from "@/components/layout/header";
import { Shell } from "@/components/layout/shell";
import { useAuthStore } from "@/stores/auth-store";
import { settingApi } from "@/lib/api/setting";

export default function AuthenticatedLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  const router = useRouter();
  const { isAuthenticated, isLoading, setUser } = useAuthStore();

  useEffect(() => {
    const checkAuth = async () => {
      try {
        const response = await settingApi.me();
        setUser(response.data);
      } catch {
        setUser(null);
        router.push("/login");
      }
    };
    checkAuth();
  }, [setUser, router]);

  if (isLoading) {
    return (
      <div className="flex h-screen items-center justify-center">
        <div className="size-8 animate-spin rounded-full border-4 border-primary border-t-transparent" />
      </div>
    );
  }

  if (!isAuthenticated) {
    return null;
  }

  return (
    <div className="flex h-screen flex-col">
      <Header />
      <div className="flex flex-1 overflow-hidden">
        <Dock />
        <main className="flex flex-1 overflow-hidden">{children}</main>
        <Shell />
      </div>
    </div>
  );
}
