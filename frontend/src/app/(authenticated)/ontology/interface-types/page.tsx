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
import type { InterfaceType } from "@/types/ontology";

const columns: ColumnDef<InterfaceType>[] = [
  { key: "api_name", label: "API Name", sortable: true },
  { key: "display_name", label: "Display Name", sortable: true },
  {
    key: "category",
    label: "Category",
    render: (value) => {
      const v = value as string;
      return v === "LINK_INTERFACE" ? "Link" : "Object";
    },
  },
  {
    key: "extends_interface_type_rids",
    label: "Extends",
    render: (value) => {
      const rids = value as string[];
      return rids && rids.length > 0 ? `${rids.length} interface(s)` : "-";
    },
  },
  {
    key: "required_shared_property_type_rids",
    label: "Required Properties",
    render: (value) => {
      const rids = value as string[];
      return String(rids?.length ?? 0);
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

export default function InterfaceTypesPage() {
  const router = useRouter();
  const [page, setPage] = useState(1);
  const pageSize = 20;

  const { data, isLoading } = useQuery({
    queryKey: ["ontology", "interface-types", "list", page],
    queryFn: () => ontologyApi.queryInterfaceTypes({ offset: (page - 1) * pageSize, limit: pageSize }),
  });

  if (isLoading && !data) {
    return <PageLoading />;
  }

  return (
    <div className="flex flex-col gap-4">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-xl font-semibold">Interface Types</h1>
          <p className="text-sm text-muted-foreground">Manage interface type definitions</p>
        </div>
        <Button onClick={() => router.push("/ontology/interface-types/new")}>
          <Plus className="size-4" />
          New Interface Type
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
        onRowClick={(row) => router.push(`/ontology/interface-types/${row.rid}`)}
      />
    </div>
  );
}
