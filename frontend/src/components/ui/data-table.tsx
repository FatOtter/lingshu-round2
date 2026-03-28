"use client";

import { useState, type ReactNode } from "react";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { Button } from "@/components/ui/button";
import { ChevronUp, ChevronDown, ChevronsUpDown, ChevronLeft, ChevronRight } from "lucide-react";
import { cn } from "@/lib/utils";

export interface ColumnDef<T = Record<string, unknown>> {
  key: string;
  label: string;
  sortable?: boolean;
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  render?: (value: any, row: T) => ReactNode;
  className?: string;
}

interface DataTableProps<T> {
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  columns: ColumnDef<any>[];
  data: T[];
  total?: number;
  page?: number;
  pageSize?: number;
  onPageChange?: (page: number) => void;
  onSort?: (field: string, direction: "asc" | "desc") => void;
  sortField?: string;
  sortDirection?: "asc" | "desc";
  onRowClick?: (row: T) => void;
  emptyMessage?: string;
  loading?: boolean;
}

export function DataTable<T>({
  columns,
  data,
  total = 0,
  page = 1,
  pageSize = 20,
  onPageChange,
  onSort,
  sortField,
  sortDirection,
  onRowClick,
  emptyMessage = "No data",
  loading = false,
}: DataTableProps<T>) {
  const [localSort, setLocalSort] = useState<{ field: string; direction: "asc" | "desc" } | null>(null);

  const activeSort = sortField ? { field: sortField, direction: sortDirection ?? "asc" } : localSort;
  const totalPages = Math.ceil(total / pageSize);

  const handleSort = (field: string) => {
    const newDirection =
      activeSort?.field === field && activeSort.direction === "asc" ? "desc" : "asc";
    if (onSort) {
      onSort(field, newDirection);
    } else {
      setLocalSort({ field, direction: newDirection });
    }
  };

  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const getField = (row: any, key: string) => row[key];

  const sortedData = localSort && !onSort
    ? [...data].sort((a, b) => {
        const aVal = getField(a, localSort.field);
        const bVal = getField(b, localSort.field);
        const cmp = String(aVal ?? "").localeCompare(String(bVal ?? ""));
        return localSort.direction === "asc" ? cmp : -cmp;
      })
    : data;

  return (
    <div className="flex flex-col gap-2">
      <div className="rounded-md border">
        <Table>
          <TableHeader>
            <TableRow>
              {columns.map((col) => (
                <TableHead
                  key={col.key}
                  className={cn(col.sortable && "cursor-pointer select-none", col.className)}
                  onClick={col.sortable ? () => handleSort(col.key) : undefined}
                >
                  <div className="flex items-center gap-1">
                    {col.label}
                    {col.sortable && (
                      <span className="text-muted-foreground">
                        {activeSort?.field === col.key ? (
                          activeSort.direction === "asc" ? (
                            <ChevronUp className="size-3.5" />
                          ) : (
                            <ChevronDown className="size-3.5" />
                          )
                        ) : (
                          <ChevronsUpDown className="size-3.5" />
                        )}
                      </span>
                    )}
                  </div>
                </TableHead>
              ))}
            </TableRow>
          </TableHeader>
          <TableBody>
            {loading ? (
              <TableRow>
                <TableCell colSpan={columns.length} className="h-24 text-center">
                  <div className="flex items-center justify-center">
                    <div className="size-5 animate-spin rounded-full border-2 border-primary border-t-transparent" />
                  </div>
                </TableCell>
              </TableRow>
            ) : sortedData.length === 0 ? (
              <TableRow>
                <TableCell colSpan={columns.length} className="h-24 text-center text-muted-foreground">
                  {emptyMessage}
                </TableCell>
              </TableRow>
            ) : (
              sortedData.map((row, rowIdx) => (
                <TableRow
                  key={rowIdx}
                  className={cn(onRowClick && "cursor-pointer")}
                  onClick={onRowClick ? () => onRowClick(row) : undefined}
                >
                  {columns.map((col) => {
                    const value = getField(row, col.key);
                    return (
                      <TableCell key={col.key} className={col.className}>
                        {col.render ? col.render(value, row) : String(value ?? "")}
                      </TableCell>
                    );
                  })}
                </TableRow>
              ))
            )}
          </TableBody>
        </Table>
      </div>

      {totalPages > 1 && onPageChange && (
        <div className="flex items-center justify-between text-sm text-muted-foreground">
          <span>
            {total} total &middot; Page {page} of {totalPages}
          </span>
          <div className="flex items-center gap-1">
            <Button
              variant="outline"
              size="icon-sm"
              disabled={page <= 1}
              onClick={() => onPageChange(page - 1)}
            >
              <ChevronLeft className="size-4" />
            </Button>
            <Button
              variant="outline"
              size="icon-sm"
              disabled={page >= totalPages}
              onClick={() => onPageChange(page + 1)}
            >
              <ChevronRight className="size-4" />
            </Button>
          </div>
        </div>
      )}
    </div>
  );
}
