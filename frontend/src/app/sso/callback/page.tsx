"use client";

import { Suspense, useEffect, useRef, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { settingApi } from "@/lib/api/setting";
import { useAuthStore } from "@/stores/auth-store";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";

function SsoCallbackInner() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const setUser = useAuthStore((s) => s.setUser);
  const [error, setError] = useState("");
  const calledRef = useRef(false);

  useEffect(() => {
    if (calledRef.current) return;
    calledRef.current = true;

    const code = searchParams.get("code");
    const state = searchParams.get("state");

    if (!code || !state) {
      setError("Missing authorization code or state parameter");
      return;
    }

    settingApi
      .ssoCallback(code, state)
      .then((res) => {
        setUser(res.data.user);
        router.push("/");
      })
      .catch(() => {
        setError("SSO authentication failed. Please try again.");
      });
  }, [searchParams, setUser, router]);

  return (
    <Card className="w-full max-w-sm">
      <CardHeader className="text-center">
        <CardTitle className="text-lg">
          {error ? "Authentication Failed" : "Completing sign in..."}
        </CardTitle>
      </CardHeader>
      {error && (
        <CardContent>
          <p className="text-sm text-destructive text-center">{error}</p>
          <a
            href="/login"
            className="mt-4 block text-center text-sm text-primary underline"
          >
            Back to login
          </a>
        </CardContent>
      )}
    </Card>
  );
}

export default function SsoCallbackPage() {
  return (
    <div className="flex min-h-screen items-center justify-center bg-background p-4">
      <Suspense
        fallback={
          <Card className="w-full max-w-sm">
            <CardHeader className="text-center">
              <CardTitle className="text-lg">Completing sign in...</CardTitle>
            </CardHeader>
          </Card>
        }
      >
        <SsoCallbackInner />
      </Suspense>
    </div>
  );
}
