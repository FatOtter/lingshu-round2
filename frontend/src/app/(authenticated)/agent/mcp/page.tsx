"use client";

import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { useRouter } from "next/navigation";
import { copilotApi } from "@/lib/api/copilot";
import { DataTable, type ColumnDef } from "@/components/ui/data-table";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { PageLoading } from "@/components/ui/loading";
import { Plus } from "lucide-react";
import type { McpConnection } from "@/types/copilot";

const columns: ColumnDef<McpConnection>[] = [
  { key: "api_name", label: "API Name", sortable: true },
  { key: "display_name", label: "Display Name", sortable: true },
  {
    key: "status",
    label: "Status",
    render: (value) => {
      const status = value as string;
      const variant = status === "connected" ? "default" : "secondary";
      return <Badge variant={variant}>{status}</Badge>;
    },
  },
  {
    key: "enabled",
    label: "Enabled",
    render: (value) =>
      value ? (
        <Badge variant="default">Enabled</Badge>
      ) : (
        <Badge variant="secondary">Disabled</Badge>
      ),
  },
  {
    key: "created_at",
    label: "Created",
    sortable: true,
    render: (value) => {
      const date = value as string;
      return date ? new Date(date).toLocaleDateString() : "-";
    },
  },
];

export default function AgentMcpPage() {
  const router = useRouter();
  const [page, setPage] = useState(1);
  const pageSize = 20;

  const { data, isLoading } = useQuery({
    queryKey: ["copilot", "mcp", page],
    queryFn: () =>
      copilotApi.queryMcp({ pagination: { page, page_size: pageSize } }),
  });

  if (isLoading && !data) {
    return <PageLoading />;
  }

  const connections = (data?.data ?? []) as unknown as Record<string, unknown>[];
  const total = data?.pagination?.total ?? 0;

  return (
    <div className="flex flex-col gap-4 p-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-xl font-semibold">MCP Connections</h1>
          <p className="text-sm text-muted-foreground">Manage MCP server connections and tools</p>
        </div>
        <Button onClick={() => router.push("/agent/mcp/new")}>
          <Plus className="size-4" />
          New Connection
        </Button>
      </div>

      <DataTable
        columns={columns}
        data={connections}
        total={total}
        page={page}
        pageSize={pageSize}
        onPageChange={setPage}
        loading={isLoading}
        onRowClick={(row) => router.push(`/agent/mcp/${row.rid as string}`)}
      />
    </div>
  );
}
