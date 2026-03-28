"use client";

import { useQuery } from "@tanstack/react-query";
import { ontologyApi } from "@/lib/api/ontology";
import { DataTable, type ColumnDef } from "@/components/ui/data-table";
import { Badge } from "@/components/ui/badge";
import { PageLoading } from "@/components/ui/loading";
import type { PropertyType, ObjectType } from "@/types/ontology";

const columns: ColumnDef<PropertyType>[] = [
  { key: "api_name", label: "API Name", sortable: true },
  { key: "display_name", label: "Display Name", sortable: true },
  { key: "data_type", label: "Data Type" },
  { key: "owner_type", label: "Owner Type" },
  { key: "owner_rid", label: "Owner RID" },
  {
    key: "is_required",
    label: "Required",
    render: (value) => (value ? "Yes" : "No"),
  },
  {
    key: "is_array",
    label: "Array",
    render: (value) => (value ? "Yes" : "No"),
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
];

export default function PropertiesPage() {
  const { data: objectTypesData, isLoading: loadingOT } = useQuery({
    queryKey: ["ontology", "object-types", "all"],
    queryFn: () => ontologyApi.queryObjectTypes({ limit: 500 }),
  });

  const isLoading = loadingOT;

  if (isLoading && !objectTypesData) {
    return <PageLoading />;
  }

  const allProperties: PropertyType[] = (objectTypesData?.data ?? []).flatMap(
    (ot: ObjectType) =>
      (ot.property_types ?? []).map((p) => ({
        ...p,
        owner_type: "ObjectType",
        owner_rid: ot.rid,
      }))
  );

  return (
    <div className="flex flex-col gap-4">
      <div>
        <h1 className="text-xl font-semibold">Properties</h1>
        <p className="text-sm text-muted-foreground">
          Read-only index of all property types across the ontology
        </p>
      </div>

      <DataTable
        columns={columns}
        data={allProperties as unknown as Record<string, unknown>[]}
        total={allProperties.length}
        emptyMessage="No properties found"
        loading={isLoading}
      />
    </div>
  );
}
