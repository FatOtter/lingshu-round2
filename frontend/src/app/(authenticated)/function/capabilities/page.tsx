"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { useQuery } from "@tanstack/react-query";
import { functionApi } from "@/lib/api/function";
import { PageLoading } from "@/components/ui/loading";
import { DataTable, type ColumnDef } from "@/components/ui/data-table";
import { Badge } from "@/components/ui/badge";
import type { CapabilityDescriptor } from "@/types/function";

const SAFETY_VARIANT: Record<string, "default" | "secondary" | "destructive" | "outline"> = {
  SAFETY_READ_ONLY: "secondary",
  SAFETY_IDEMPOTENT_WRITE: "default",
  SAFETY_NON_IDEMPOTENT: "outline",
  SAFETY_CRITICAL: "destructive",
};

const SAFETY_LABEL: Record<string, string> = {
  SAFETY_READ_ONLY: "Read Only",
  SAFETY_IDEMPOTENT_WRITE: "Idempotent",
  SAFETY_NON_IDEMPOTENT: "Non-Idempotent",
  SAFETY_CRITICAL: "Critical",
};

const columns: ColumnDef<CapabilityDescriptor>[] = [
  {
    key: "type",
    label: "Type",
    render: (value) => {
      const type = String(value);
      const variant = type === "action" ? "default" : "secondary";
      return <Badge variant={variant}>{type}</Badge>;
    },
  },
  {
    key: "api_name",
    label: "API Name",
    sortable: true,
  },
  {
    key: "display_name",
    label: "Display Name",
    sortable: true,
  },
  {
    key: "safety_level",
    label: "Safety Level",
    render: (value) => {
      const level = String(value);
      return <Badge variant={SAFETY_VARIANT[level] ?? "outline"}>{SAFETY_LABEL[level] ?? level}</Badge>;
    },
  },
  {
    key: "description",
    label: "Description",
    className: "max-w-[300px] truncate",
  },
];

export default function CapabilitiesPage() {
  const router = useRouter();
  const [page, setPage] = useState(1);
  const pageSize = 20;

  const { data, isLoading } = useQuery({
    queryKey: ["function", "capabilities", page],
    queryFn: () => functionApi.queryCapabilities(),
  });

  if (isLoading) {
    return <PageLoading />;
  }

  const items = data?.data ?? [];
  const total = items.length;

  const handleRowClick = (row: Record<string, unknown>) => {
    const capability = row as unknown as CapabilityDescriptor;
    if (capability.type === "action") {
      router.push(`/function/capabilities/actions/${capability.rid}`);
    } else if (capability.type === "global_function") {
      router.push(`/function/capabilities/globals/${capability.rid}`);
    }
  };

  return (
    <div className="flex flex-col gap-6">
      <div>
        <h1 className="text-xl font-semibold">Capabilities</h1>
        <p className="text-sm text-muted-foreground">All registered actions and functions</p>
      </div>

      <DataTable
        columns={columns}
        data={items as unknown as Record<string, unknown>[]}
        total={total}
        page={page}
        pageSize={pageSize}
        onPageChange={setPage}
        onRowClick={handleRowClick}
        emptyMessage="No capabilities registered"
      />
    </div>
  );
}
