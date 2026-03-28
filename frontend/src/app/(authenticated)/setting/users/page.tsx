"use client";

import { useState, useCallback, useMemo } from "react";
import { useRouter } from "next/navigation";
import { useQuery } from "@tanstack/react-query";
import { Plus } from "lucide-react";
import { settingApi } from "@/lib/api/setting";
import { useDebounce } from "@/hooks/use-debounce";
import type { User } from "@/types/setting";
import { DataTable, type ColumnDef } from "@/components/ui/data-table";
import { QueryFilter, type FilterField } from "@/components/ui/query-filter";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import type { Filter } from "@/types/common";

const filterFields: FilterField[] = [
  {
    key: "role",
    label: "Role",
    type: "select",
    options: [
      { label: "Admin", value: "admin" },
      { label: "Member", value: "member" },
      { label: "Viewer", value: "viewer" },
    ],
  },
];

const columns: ColumnDef<User>[] = [
  {
    key: "display_name",
    label: "Name",
    sortable: true,
  },
  {
    key: "email",
    label: "Email",
    sortable: true,
  },
  {
    key: "role",
    label: "Role",
    render: (value) => {
      const role = value as string;
      const variant = role === "admin" ? "default" : "secondary";
      return <Badge variant={variant}>{role}</Badge>;
    },
  },
  {
    key: "is_active",
    label: "Status",
    render: (value) => {
      const active = value as boolean;
      return (
        <Badge variant={active ? "default" : "outline"}>
          {active ? "Active" : "Inactive"}
        </Badge>
      );
    },
  },
  {
    key: "created_at",
    label: "Created",
    sortable: true,
    render: (value) => new Date(value as string).toLocaleDateString(),
  },
];

export default function UsersPage() {
  const router = useRouter();
  const [page, setPage] = useState(1);
  const [search, setSearch] = useState("");
  const [filters, setFilters] = useState<Filter[]>([]);
  const pageSize = 20;

  const debouncedSearch = useDebounce(search, 300);

  // Build API filters from UI filters + search term
  const apiFilters = useMemo(() => {
    const result: Array<{ field: string; operator: string; value: unknown }> = [];

    // Add role filter and other filters from QueryFilter
    for (const f of filters) {
      result.push({ field: f.field, operator: f.operator, value: f.value });
    }

    // Add search filter (search by display_name or email using "contains")
    if (debouncedSearch) {
      result.push({
        field: "display_name",
        operator: "contains",
        value: debouncedSearch,
      });
    }

    return result;
  }, [filters, debouncedSearch]);

  const { data, isLoading } = useQuery({
    queryKey: ["setting", "users", page, debouncedSearch, filters],
    queryFn: () =>
      settingApi.queryUsers({
        filters: apiFilters.length > 0 ? apiFilters : undefined,
        pagination: { page, page_size: pageSize },
      }),
  });

  const users = data?.data ?? [];
  const total = data?.pagination?.total ?? 0;

  const handleRowClick = useCallback(
    (row: User) => {
      router.push(`/setting/users/${row.rid}`);
    },
    [router],
  );

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
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-lg font-semibold">Users</h1>
          <p className="text-sm text-muted-foreground">
            Manage user accounts and permissions
          </p>
        </div>
        <Button onClick={() => router.push("/setting/users/new")}>
          <Plus className="size-4" />
          New User
        </Button>
      </div>

      <QueryFilter
        fields={filterFields}
        onSearch={handleSearch}
        onFilter={handleFilter}
        searchPlaceholder="Search users..."
      />

      <DataTable
        columns={columns}
        data={users}
        total={total}
        page={page}
        pageSize={pageSize}
        onPageChange={setPage}
        onRowClick={handleRowClick}
        loading={isLoading}
        emptyMessage="No users found"
      />
    </div>
  );
}
