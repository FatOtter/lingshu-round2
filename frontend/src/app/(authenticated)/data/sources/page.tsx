"use client";

import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { useRouter } from "next/navigation";
import { dataApi } from "@/lib/api/data";
import { DataTable, type ColumnDef } from "@/components/ui/data-table";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { PageLoading } from "@/components/ui/loading";
import { Plus, Plug } from "lucide-react";
import type { Connection } from "@/types/data";

const STATUS_VARIANT: Record<string, "default" | "secondary" | "destructive" | "outline"> = {
  active: "default",
  inactive: "secondary",
  error: "destructive",
};

export default function SourcesPage() {
  const router = useRouter();
  const queryClient = useQueryClient();
  const [page, setPage] = useState(1);
  const pageSize = 20;

  const { data, isLoading } = useQuery({
    queryKey: ["data", "connections", "list", page],
    queryFn: () => dataApi.queryConnections({ pagination: { page, page_size: pageSize } }),
  });

  const testMutation = useMutation({
    mutationFn: (rid: string) => dataApi.testConnection(rid),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["data", "connections"] });
    },
  });

  const columns: ColumnDef<Connection>[] = [
    { key: "api_name", label: "API Name", sortable: true },
    { key: "display_name", label: "Display Name", sortable: true },
    { key: "connector_type", label: "Connector Type", sortable: true },
    {
      key: "status",
      label: "Status",
      render: (value) => {
        const status = value as string;
        return <Badge variant={STATUS_VARIANT[status] ?? "outline"}>{status}</Badge>;
      },
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
    {
      key: "rid",
      label: "Actions",
      render: (_value, row) => (
        <Button
          variant="ghost"
          size="xs"
          onClick={(e) => {
            e.stopPropagation();
            testMutation.mutate(row.rid);
          }}
          disabled={testMutation.isPending}
        >
          <Plug className="size-3" />
          Test
        </Button>
      ),
    },
  ];

  if (isLoading && !data) {
    return <PageLoading />;
  }

  return (
    <div className="flex flex-col gap-4">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-xl font-semibold">Data Sources</h1>
          <p className="text-sm text-muted-foreground">Manage data connections</p>
        </div>
        <Button onClick={() => router.push("/data/sources/new")}>
          <Plus className="size-4" />
          New Connection
        </Button>
      </div>

      <DataTable
        columns={columns}
        data={(data?.data ?? []) as unknown as Record<string, unknown>[]}
        total={data?.pagination?.total ?? 0}
        page={page}
        pageSize={pageSize}
        onPageChange={setPage}
        loading={isLoading}
        onRowClick={(row) => router.push(`/data/sources/${row.rid}`)}
      />
    </div>
  );
}
