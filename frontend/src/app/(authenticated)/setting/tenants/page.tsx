"use client";

import { useState, useCallback } from "react";
import { useRouter } from "next/navigation";
import { useQuery } from "@tanstack/react-query";
import { Plus } from "lucide-react";
import { settingApi } from "@/lib/api/setting";
import type { Tenant } from "@/types/setting";
import { DataTable, type ColumnDef } from "@/components/ui/data-table";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";

const columns: ColumnDef<Tenant>[] = [
  {
    key: "display_name",
    label: "Display Name",
    sortable: true,
  },
  {
    key: "status",
    label: "Status",
    render: (value) => {
      const status = value as string;
      const variant = status === "active" ? "default" : "outline";
      return <Badge variant={variant}>{status}</Badge>;
    },
  },
  {
    key: "created_at",
    label: "Created",
    sortable: true,
    render: (value) => new Date(value as string).toLocaleDateString(),
  },
];

export default function TenantsPage() {
  const router = useRouter();
  const [page, setPage] = useState(1);
  const pageSize = 20;

  const { data, isLoading } = useQuery({
    queryKey: ["setting", "tenants", page],
    queryFn: () =>
      settingApi.queryTenants({
        pagination: { page, page_size: pageSize },
      }),
  });

  const tenants = data?.data ?? [];
  const total = data?.pagination?.total ?? 0;

  const handleRowClick = useCallback(
    (row: Tenant) => {
      router.push(`/setting/tenants/${row.rid}`);
    },
    [router],
  );

  return (
    <div className="flex flex-col gap-4">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-lg font-semibold">Tenants</h1>
          <p className="text-sm text-muted-foreground">
            Manage tenant organizations and their members
          </p>
        </div>
        <Button onClick={() => router.push("/setting/tenants/new")}>
          <Plus className="size-4" />
          New Tenant
        </Button>
      </div>

      <DataTable
        columns={columns}
        data={tenants}
        total={total}
        page={page}
        pageSize={pageSize}
        onPageChange={setPage}
        onRowClick={handleRowClick}
        loading={isLoading}
        emptyMessage="No tenants found"
      />
    </div>
  );
}
