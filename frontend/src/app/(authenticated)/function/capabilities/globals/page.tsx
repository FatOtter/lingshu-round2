"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { functionApi } from "@/lib/api/function";
import { PageLoading } from "@/components/ui/loading";
import { DataTable, type ColumnDef } from "@/components/ui/data-table";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Plus, Play } from "lucide-react";
import type { GlobalFunction } from "@/types/function";

const columns: ColumnDef<GlobalFunction>[] = [
  {
    key: "api_name",
    label: "API Name",
    sortable: true,
    render: (value) => <span className="font-mono text-xs">{String(value)}</span>,
  },
  {
    key: "display_name",
    label: "Display Name",
    sortable: true,
  },
  {
    key: "description",
    label: "Description",
    className: "max-w-[300px] truncate",
  },
  {
    key: "is_active",
    label: "Status",
    render: (value) => (
      <Badge variant={value ? "default" : "outline"}>{value ? "Active" : "Inactive"}</Badge>
    ),
  },
  {
    key: "version",
    label: "Version",
    render: (value) => <span className="text-muted-foreground">v{String(value)}</span>,
  },
  {
    key: "updated_at",
    label: "Updated",
    sortable: true,
    render: (value) => (value ? new Date(String(value)).toLocaleString() : "-"),
  },
];

export default function GlobalFunctionsPage() {
  const router = useRouter();
  const queryClient = useQueryClient();
  const [page, setPage] = useState(1);
  const pageSize = 20;

  const { data, isLoading } = useQuery({
    queryKey: ["function", "globals", page],
    queryFn: () => functionApi.queryFunctions({ pagination: { page, page_size: pageSize } }),
  });

  const createMutation = useMutation({
    mutationFn: () =>
      functionApi.createFunction({
        api_name: "new_function",
        display_name: "New Function",
        description: "",
        parameters: {},
        implementation: {},
      }),
    onSuccess: (response) => {
      queryClient.invalidateQueries({ queryKey: ["function", "globals"] });
      router.push(`/function/capabilities/globals/${response.data.rid}`);
    },
  });

  const executeMutation = useMutation({
    mutationFn: (rid: string) => functionApi.executeFunction(rid, {}),
  });

  if (isLoading) {
    return <PageLoading />;
  }

  const items = (data?.data ?? []) as unknown as Record<string, unknown>[];
  const total = data?.pagination?.total ?? 0;

  const handleRowClick = (row: Record<string, unknown>) => {
    const fn = row as unknown as GlobalFunction;
    router.push(`/function/capabilities/globals/${fn.rid}`);
  };

  return (
    <div className="flex flex-col gap-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-xl font-semibold">Global Functions</h1>
          <p className="text-sm text-muted-foreground">Manage and test global functions</p>
        </div>
        <Button onClick={() => createMutation.mutate()} disabled={createMutation.isPending}>
          <Plus className="size-4" />
          {createMutation.isPending ? "Creating..." : "New Function"}
        </Button>
      </div>

      <DataTable
        columns={[
          ...columns,
          {
            key: "_actions",
            label: "",
            className: "w-[80px]",
            render: (_value, row) => {
              const fn = row as unknown as GlobalFunction;
              return (
                <Button
                  variant="ghost"
                  size="icon-sm"
                  onClick={(e) => {
                    e.stopPropagation();
                    executeMutation.mutate(fn.rid);
                  }}
                  disabled={executeMutation.isPending}
                >
                  <Play className="size-3.5" />
                </Button>
              );
            },
          },
        ]}
        data={items as unknown as Record<string, unknown>[]}
        total={total}
        page={page}
        pageSize={pageSize}
        onPageChange={setPage}
        onRowClick={handleRowClick}
        emptyMessage="No global functions"
      />
    </div>
  );
}
