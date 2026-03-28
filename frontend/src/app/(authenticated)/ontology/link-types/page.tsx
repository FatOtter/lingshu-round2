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
import type { LinkType } from "@/types/ontology";

const columns: ColumnDef<LinkType>[] = [
  { key: "api_name", label: "API Name", sortable: true },
  { key: "display_name", label: "Display Name", sortable: true },
  {
    key: "source_object_type_rid",
    label: "Source -> Target",
    render: (_value, row) =>
      `${row.source_object_type_rid ?? "-"} -> ${row.target_object_type_rid ?? "-"}`,
  },
  { key: "cardinality", label: "Cardinality" },
  {
    key: "version_status",
    label: "Status",
    render: (value) => {
      const status = value as string;
      const variant = status === "ACTIVE" ? "default" : status === "DRAFT" ? "secondary" : "outline";
      return <Badge variant={variant}>{status}</Badge>;
    },
  },
];

export default function LinkTypesPage() {
  const router = useRouter();
  const [page, setPage] = useState(1);
  const pageSize = 20;

  const { data, isLoading } = useQuery({
    queryKey: ["ontology", "link-types", "list", page],
    queryFn: () => ontologyApi.queryLinkTypes({ offset: (page - 1) * pageSize, limit: pageSize }),
  });

  if (isLoading && !data) {
    return <PageLoading />;
  }

  return (
    <div className="flex flex-col gap-4">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-xl font-semibold">Link Types</h1>
          <p className="text-sm text-muted-foreground">Manage link type definitions</p>
        </div>
        <Button onClick={() => router.push("/ontology/link-types/new")}>
          <Plus className="size-4" />
          New Link Type
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
        onRowClick={(row) => router.push(`/ontology/link-types/${row.rid}`)}
      />
    </div>
  );
}
