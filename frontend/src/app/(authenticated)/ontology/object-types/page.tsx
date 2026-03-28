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
import type { ObjectType } from "@/types/ontology";

const columns: ColumnDef<ObjectType>[] = [
  { key: "api_name", label: "API Name", sortable: true },
  { key: "display_name", label: "Display Name", sortable: true },
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
    key: "property_types",
    label: "Properties",
    render: (_value, row) => String(row.property_types?.length ?? 0),
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

export default function ObjectTypesPage() {
  const router = useRouter();
  const [page, setPage] = useState(1);
  const pageSize = 20;

  const { data, isLoading } = useQuery({
    queryKey: ["ontology", "object-types", "list", page],
    queryFn: () => ontologyApi.queryObjectTypes({ offset: (page - 1) * pageSize, limit: pageSize }),
  });

  if (isLoading && !data) {
    return <PageLoading />;
  }

  return (
    <div className="flex flex-col gap-4">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-xl font-semibold">Object Types</h1>
          <p className="text-sm text-muted-foreground">Manage object type definitions</p>
        </div>
        <Button onClick={() => router.push("/ontology/object-types/new")}>
          <Plus className="size-4" />
          New Object Type
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
        onRowClick={(row) => router.push(`/ontology/object-types/${row.rid}`)}
      />
    </div>
  );
}
