"use client";

import { useState, useCallback, useMemo } from "react";
import { useParams, useRouter } from "next/navigation";
import { useQuery } from "@tanstack/react-query";
import { dataApi } from "@/lib/api/data";
import { useDebounce } from "@/hooks/use-debounce";
import { DataTable, type ColumnDef } from "@/components/ui/data-table";
import { PageLoading } from "@/components/ui/loading";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { ArrowLeft, Lock, Search } from "lucide-react";

export default function InstanceListPage() {
  const params = useParams<{ typeKind: string; typeRid: string }>();
  const router = useRouter();
  const { typeKind, typeRid } = params;
  const [page, setPage] = useState(1);
  const [search, setSearch] = useState("");
  const [sortField, setSortField] = useState<string | null>(null);
  const [sortDir, setSortDir] = useState<"asc" | "desc">("asc");
  const pageSize = 20;

  const debouncedSearch = useDebounce(search, 300);

  // Build query params for the API
  const queryParams = useMemo(() => {
    const p: Record<string, unknown> = {
      pagination: { page, page_size: pageSize },
    };

    if (debouncedSearch) {
      p.search = debouncedSearch;
    }

    if (sortField) {
      p.sort = [{ field: sortField, order: sortDir }];
    }

    return p;
  }, [page, pageSize, debouncedSearch, sortField, sortDir]);

  const { data, isLoading } = useQuery({
    queryKey: ["data", "instances", typeKind, typeRid, page, debouncedSearch, sortField, sortDir],
    queryFn: () => dataApi.queryInstances(typeKind, typeRid, queryParams),
  });

  const queryResult = data?.data;

  const columns: ColumnDef<Record<string, unknown>>[] = (queryResult?.columns ?? []).map(
    (col) => ({
      key: col.api_name,
      label: col.display_name,
      sortable: col.sortable,
      render: (value) => {
        if (col.is_masked) {
          return (
            <span className="inline-flex items-center gap-1 text-muted-foreground">
              <Lock className="size-3" />
              Masked
            </span>
          );
        }
        if (value === null || value === undefined) {
          return <span className="text-muted-foreground">-</span>;
        }
        if (typeof value === "object") {
          return <span className="font-mono text-xs">{JSON.stringify(value)}</span>;
        }
        return String(value);
      },
    }),
  );

  const tableData: Record<string, unknown>[] = (queryResult?.instances ?? []).map(
    (instance) => ({
      primary_key: instance.primary_key,
      ...instance.fields,
    }),
  );

  const handleSearchChange = useCallback((value: string) => {
    setSearch(value);
    setPage(1);
  }, []);

  const handleSort = useCallback(
    (field: string, direction: "asc" | "desc") => {
      setSortField(field);
      setSortDir(direction);
      setPage(1);
    },
    [],
  );

  if (isLoading && !data) {
    return <PageLoading />;
  }

  const kindLabel = typeKind === "object-types" ? "Object Type" : "Link Type";

  return (
    <div className="flex flex-col gap-4">
      <div className="flex items-center gap-2">
        <Button variant="ghost" size="icon" onClick={() => router.push("/data/browse")}>
          <ArrowLeft className="size-4" />
        </Button>
        <div>
          <h1 className="text-xl font-semibold">{kindLabel} Instances</h1>
          <p className="text-sm text-muted-foreground">
            Browsing data for {typeRid}
          </p>
        </div>
      </div>

      {/* Search */}
      <div className="relative max-w-sm">
        <Search className="absolute left-2.5 top-1/2 size-4 -translate-y-1/2 text-muted-foreground" />
        <Input
          placeholder="Search instances..."
          value={search}
          onChange={(e) => handleSearchChange(e.target.value)}
          className="pl-8"
        />
      </div>

      <DataTable
        columns={columns}
        data={tableData}
        total={queryResult?.total ?? 0}
        page={page}
        pageSize={pageSize}
        onPageChange={setPage}
        onSort={handleSort}
        sortField={sortField ?? undefined}
        sortDirection={sortDir}
        loading={isLoading}
        emptyMessage={debouncedSearch ? "No instances match your search" : "No instances found for this type"}
      />
    </div>
  );
}
