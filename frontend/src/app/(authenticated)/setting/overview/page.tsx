"use client";

import { useQuery } from "@tanstack/react-query";
import { Users, ScrollText } from "lucide-react";
import { settingApi } from "@/lib/api/setting";
import {
  Card,
  CardHeader,
  CardTitle,
  CardDescription,
  CardContent,
} from "@/components/ui/card";

export default function SettingOverviewPage() {
  const { data: usersData, isLoading: usersLoading } = useQuery({
    queryKey: ["setting", "users"],
    queryFn: () => settingApi.queryUsers({ pagination: { page: 1, page_size: 1 } }),
  });

  const { data: auditData, isLoading: auditLoading } = useQuery({
    queryKey: ["setting", "audit-recent"],
    queryFn: () => settingApi.queryAuditLogs({ pagination: { page: 1, page_size: 5 } }),
  });

  const totalUsers = usersData?.pagination?.total ?? 0;
  const recentAudits = auditData?.data ?? [];

  return (
    <div className="flex flex-col gap-6">
      <div>
        <h1 className="text-lg font-semibold">Settings Overview</h1>
        <p className="text-sm text-muted-foreground">
          System configuration and administration
        </p>
      </div>

      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <Users className="size-4 text-muted-foreground" />
              Total Users
            </CardTitle>
            <CardDescription>Registered user accounts</CardDescription>
          </CardHeader>
          <CardContent>
            {usersLoading ? (
              <div className="size-5 animate-spin rounded-full border-2 border-primary border-t-transparent" />
            ) : (
              <span className="text-2xl font-bold">{totalUsers}</span>
            )}
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <ScrollText className="size-4 text-muted-foreground" />
              Recent Audit Logs
            </CardTitle>
            <CardDescription>Latest system activity</CardDescription>
          </CardHeader>
          <CardContent>
            {auditLoading ? (
              <div className="size-5 animate-spin rounded-full border-2 border-primary border-t-transparent" />
            ) : recentAudits.length === 0 ? (
              <p className="text-sm text-muted-foreground">No recent activity</p>
            ) : (
              <ul className="flex flex-col gap-1.5">
                {recentAudits.map((log) => (
                  <li
                    key={log.log_id}
                    className="flex items-center justify-between text-sm"
                  >
                    <span className="text-muted-foreground">
                      {log.module}/{log.action}
                    </span>
                    <span className="text-xs text-muted-foreground">
                      {new Date(log.created_at).toLocaleDateString()}
                    </span>
                  </li>
                ))}
              </ul>
            )}
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
