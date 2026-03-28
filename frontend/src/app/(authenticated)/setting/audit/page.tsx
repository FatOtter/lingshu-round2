"use client";

import { useState, useCallback } from "react";
import { useQuery } from "@tanstack/react-query";
import { settingApi } from "@/lib/api/setting";
import type { AuditLog } from "@/types/setting";
import { DataTable, type ColumnDef } from "@/components/ui/data-table";
import { QueryFilter, type FilterField } from "@/components/ui/query-filter";
import { Badge } from "@/components/ui/badge";
import type { Filter } from "@/types/common";

const filterFields: FilterField[] = [
  {
    key: "module",
    label: "Module",
    type: "select",
    options: [
      { label: "Setting", value: "setting" },
      { label: "Data", value: "data" },
      { label: "Ontology", value: "ontology" },
      { label: "Function", value: "function" },
    ],
  },
  {
    key: "action",
    label: "Action",
    type: "select",
    options: [
      { label: "Create", value: "create" },
      { label: "Update", value: "update" },
      { label: "Delete", value: "delete" },
      { label: "Login", value: "login" },
    ],
  },
];

const columns: ColumnDef<AuditLog>[] = [
  {
    key: "created_at",
    label: "Timestamp",
    sortable: true,
    render: (value) => {
      const date = new Date(value as string);
      return (
        <span className="whitespace-nowrap">
          {date.toLocaleDateString()} {date.toLocaleTimeString()}
        </span>
      );
    },
  },
  {
    key: "user_id",
    label: "User",
    sortable: true,
  },
  {
    key: "module",
    label: "Module",
    render: (value) => <Badge variant="secondary">{value as string}</Badge>,
  },
  {
    key: "action",
    label: "Action",
    render: (value) => {
      const action = value as string;
      const variant =
        action === "delete" ? "destructive" : action === "create" ? "default" : "outline";
      return <Badge variant={variant}>{action}</Badge>;
    },
  },
  {
    key: "resource_type",
    label: "Resource",
    render: (value, row) => {
      const auditRow = row as unknown as AuditLog;
      return (
        <span className="text-sm text-muted-foreground">
          {value as string}
          {auditRow.resource_rid ? ` (${auditRow.resource_rid})` : ""}
        </span>
      );
    },
  },
];

export default function AuditLogPage() {
  const [page, setPage] = useState(1);
  const [search, setSearch] = useState("");
  const [filters, setFilters] = useState<Filter[]>([]);
  const pageSize = 20;

  const moduleFilter = filters.find((f) => f.field === "module")?.value as
    | string
    | undefined;
  const userFilter = filters.find((f) => f.field === "user_id")?.value as
    | string
    | undefined;

  const { data, isLoading } = useQuery({
    queryKey: ["setting", "audit", page, search, filters],
    queryFn: () =>
      settingApi.queryAuditLogs({
        module: moduleFilter,
        user_id: userFilter,
        pagination: { page, page_size: pageSize },
      }),
  });

  const logs = data?.data ?? [];
  const total = data?.pagination?.total ?? 0;

  const handleSearch = useCallback((query: string) => {
    setSearch(query);
    setPage(1);
  }, []);

  const handleFilter = useCallback((newFilters: Filter[]) => {
    setFilters(newFilters);
    setPage(1);
  }, []);

  return (
    <div className="flex flex-col gap-4">
      <div>
        <h1 className="text-lg font-semibold">Audit Logs</h1>
        <p className="text-sm text-muted-foreground">
          Track system activity and user actions
        </p>
      </div>

      <QueryFilter
        fields={filterFields}
        onSearch={handleSearch}
        onFilter={handleFilter}
        searchPlaceholder="Search audit logs..."
      />

      <DataTable
        columns={columns}
        data={logs as unknown as Record<string, unknown>[]}
        total={total}
        page={page}
        pageSize={pageSize}
        onPageChange={setPage}
        loading={isLoading}
        emptyMessage="No audit logs found"
      />
    </div>
  );
}
