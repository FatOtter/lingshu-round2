"use client";

import { useQuery } from "@tanstack/react-query";
import { dataApi } from "@/lib/api/data";
import { PageLoading } from "@/components/ui/loading";
import { Card, CardHeader, CardTitle, CardContent } from "@/components/ui/card";
import { Database, Activity } from "lucide-react";

export default function DataOverviewPage() {
  const { data, isLoading } = useQuery({
    queryKey: ["data", "connections", "overview"],
    queryFn: () => dataApi.queryConnections({ pagination: { page: 1, page_size: 100 } }),
  });

  if (isLoading) {
    return <PageLoading />;
  }

  const connections = data?.data ?? [];
  const totalConnections = data?.pagination?.total ?? 0;
  const activeConnections = connections.filter((c) => c.status === "active").length;

  const stats = [
    {
      label: "Total Connections",
      count: totalConnections,
      icon: <Database className="size-5 text-blue-500" />,
    },
    {
      label: "Active Connections",
      count: activeConnections,
      icon: <Activity className="size-5 text-green-500" />,
    },
  ];

  return (
    <div className="flex flex-col gap-6">
      <div>
        <h1 className="text-xl font-semibold">Data Overview</h1>
        <p className="text-sm text-muted-foreground">Summary of data connections and pipelines</p>
      </div>

      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
        {stats.map((stat) => (
          <Card key={stat.label} size="sm">
            <CardHeader>
              <div className="flex items-center gap-2">
                {stat.icon}
                <CardTitle>{stat.label}</CardTitle>
              </div>
            </CardHeader>
            <CardContent>
              <p className="text-2xl font-bold">{stat.count}</p>
            </CardContent>
          </Card>
        ))}
      </div>
    </div>
  );
}
