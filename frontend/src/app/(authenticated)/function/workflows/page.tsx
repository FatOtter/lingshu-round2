"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { functionApi } from "@/lib/api/function";
import { PageLoading } from "@/components/ui/loading";
import { DataTable, type ColumnDef } from "@/components/ui/data-table";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Plus } from "lucide-react";
import type { Workflow } from "@/types/function";

const STATUS_VARIANT: Record<string, "default" | "secondary" | "outline"> = {
  active: "default",
  draft: "secondary",
  archived: "outline",
};

const columns: ColumnDef<Workflow>[] = [
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
    key: "status",
    label: "Status",
    render: (value) => {
      const s = String(value);
      return <Badge variant={STATUS_VARIANT[s] ?? "outline"}>{s}</Badge>;
    },
  },
  {
    key: "safety_level",
    label: "Safety",
    render: (value) => {
      const label = String(value).replace("SAFETY_", "").replace(/_/g, " ");
      return <span className="text-xs text-muted-foreground">{label}</span>;
    },
  },
  {
    key: "nodes",
    label: "Nodes",
    render: (value) => {
      const nodes = value as unknown[];
      return <span>{Array.isArray(nodes) ? nodes.length : 0}</span>;
    },
  },
  {
    key: "created_at",
    label: "Created",
    sortable: true,
    render: (value) => (value ? new Date(String(value)).toLocaleDateString() : "-"),
  },
];

export default function WorkflowsPage() {
  const router = useRouter();
  const queryClient = useQueryClient();
  const [page, setPage] = useState(1);
  const pageSize = 20;

  const { data, isLoading } = useQuery({
    queryKey: ["function", "workflows", page],
    queryFn: () =>
      functionApi.queryWorkflows({
        pagination: { page, page_size: pageSize },
      }),
  });

  const createMutation = useMutation({
    mutationFn: () =>
      functionApi.createWorkflow({
        api_name: "new_workflow",
        display_name: "New Workflow",
        description: "",
        nodes: [],
        edges: [],
        status: "draft",
      }),
    onSuccess: (response) => {
      queryClient.invalidateQueries({ queryKey: ["function", "workflows"] });
      if (response?.data?.rid) {
        router.push(`/function/workflows/${response.data.rid}`);
      }
    },
  });

  if (isLoading) {
    return <PageLoading />;
  }

  const items = (data?.data ?? []) as unknown as Record<string, unknown>[];
  const total = data?.pagination?.total ?? 0;

  return (
    <div className="flex flex-col gap-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-xl font-semibold">Workflows</h1>
          <p className="text-sm text-muted-foreground">
            Manage DAG-based workflow definitions
          </p>
        </div>
        <Button
          onClick={() => createMutation.mutate()}
          disabled={createMutation.isPending}
        >
          <Plus className="size-4" />
          {createMutation.isPending ? "Creating..." : "New Workflow"}
        </Button>
      </div>

      <DataTable
        columns={columns}
        data={items}
        total={total}
        page={page}
        pageSize={pageSize}
        onPageChange={setPage}
        onRowClick={(row) => {
          const wf = row as unknown as Workflow;
          router.push(`/function/workflows/${wf.rid}`);
        }}
        emptyMessage="No workflows"
      />
    </div>
  );
}
