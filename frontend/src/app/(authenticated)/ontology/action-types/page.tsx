"use client";

import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { useRouter } from "next/navigation";
import { ontologyApi } from "@/lib/api/ontology";
import { DataTable, type ColumnDef } from "@/components/ui/data-table";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { PageLoading } from "@/components/ui/loading";
import { Plus } from "lucide-react";
import type { ActionType } from "@/types/ontology";

const columns: ColumnDef<ActionType>[] = [
  { key: "api_name", label: "API Name", sortable: true },
  { key: "display_name", label: "Display Name", sortable: true },
  { key: "operates_on_rid", label: "Operates On" },
  { key: "safety_level", label: "Safety Level" },
  {
    key: "parameters",
    label: "Parameters",
    render: (value) => {
      const params = value as unknown[];
      return String(params?.length ?? 0);
    },
  },
  {
    key: "version_status",
    label: "Status",
    render: (value) => {
      const status = value as string;
      const variant = status === "ACTIVE" ? "default" : status === "DRAFT" ? "secondary" : "outline";
      return <Badge variant={variant}>{status}</Badge>;
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
];

export default function ActionTypesPage() {
  const router = useRouter();
  const [page, setPage] = useState(1);
  const pageSize = 20;

  const { data, isLoading } = useQuery({
    queryKey: ["ontology", "action-types", "list", page],
    queryFn: () => ontologyApi.queryActionTypes({ offset: (page - 1) * pageSize, limit: pageSize }),
  });

  if (isLoading && !data) {
    return <PageLoading />;
  }

  return (
    <div className="flex flex-col gap-4">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-xl font-semibold">Action Types</h1>
          <p className="text-sm text-muted-foreground">Manage action type definitions</p>
        </div>
        <Button onClick={() => router.push("/ontology/action-types/new")}>
          <Plus className="size-4" />
          New Action Type
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
        onRowClick={(row) => router.push(`/ontology/action-types/${row.rid}`)}
      />
    </div>
  );
}
