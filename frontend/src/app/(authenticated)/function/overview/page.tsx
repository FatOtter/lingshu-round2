"use client";

import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { functionApi } from "@/lib/api/function";
import { PageLoading } from "@/components/ui/loading";
import { Card, CardHeader, CardTitle, CardContent } from "@/components/ui/card";
import { DataTable, type ColumnDef } from "@/components/ui/data-table";
import { Badge } from "@/components/ui/badge";
import { Blocks, Activity } from "lucide-react";
import type { Execution } from "@/types/function";

const STATUS_VARIANT: Record<string, "default" | "secondary" | "destructive" | "outline"> = {
  completed: "default",
  running: "secondary",
  failed: "destructive",
  pending_confirmation: "outline",
  cancelled: "outline",
};

const executionColumns: ColumnDef<Execution>[] = [
  {
    key: "execution_id",
    label: "Execution ID",
    className: "max-w-[200px] truncate",
  },
  {
    key: "capability_type",
    label: "Type",
    render: (value) => <Badge variant="secondary">{String(value)}</Badge>,
  },
  {
    key: "status",
    label: "Status",
    render: (value) => {
      const status = String(value);
      return <Badge variant={STATUS_VARIANT[status] ?? "outline"}>{status}</Badge>;
    },
  },
  {
    key: "started_at",
    label: "Started At",
    sortable: true,
    render: (value) => (value ? new Date(String(value)).toLocaleString() : "-"),
  },
  {
    key: "completed_at",
    label: "Completed At",
    render: (value) => (value ? new Date(String(value)).toLocaleString() : "-"),
  },
];

export default function FunctionOverviewPage() {
  const [page, setPage] = useState(1);
  const pageSize = 10;

  const { data: capabilities, isLoading: loadingCaps } = useQuery({
    queryKey: ["function", "capabilities", "count"],
    queryFn: () => functionApi.queryCapabilities(),
  });

  const { data: executions, isLoading: loadingExec } = useQuery({
    queryKey: ["function", "executions", "recent", page],
    queryFn: () => functionApi.queryExecutions({ pagination: { page, page_size: pageSize } }),
  });

  if (loadingCaps && loadingExec) {
    return <PageLoading />;
  }

  const totalCapabilities = capabilities?.data?.length ?? 0;
  const totalExecutions = executions?.pagination?.total ?? 0;
  const executionItems = (executions?.data ?? []) as unknown as Record<string, unknown>[];

  const stats = [
    { label: "Total Capabilities", count: totalCapabilities, icon: <Blocks className="size-5 text-blue-500" /> },
    { label: "Recent Executions", count: totalExecutions, icon: <Activity className="size-5 text-green-500" /> },
  ];

  return (
    <div className="flex flex-col gap-6">
      <div>
        <h1 className="text-xl font-semibold">Function Overview</h1>
        <p className="text-sm text-muted-foreground">Summary of capabilities and recent executions</p>
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

      <Card>
        <CardHeader>
          <CardTitle>Recent Executions</CardTitle>
        </CardHeader>
        <CardContent>
          <DataTable
            columns={executionColumns}
            data={executionItems as unknown as Record<string, unknown>[]}
            total={totalExecutions}
            page={page}
            pageSize={pageSize}
            onPageChange={setPage}
            loading={loadingExec}
            emptyMessage="No executions yet"
          />
        </CardContent>
      </Card>
    </div>
  );
}
