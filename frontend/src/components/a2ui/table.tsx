"use client";

import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import type { A2UITable } from "@/types/a2ui";

interface A2UITableViewProps {
  data: A2UITable;
}

export function A2UITableView({ data }: A2UITableViewProps) {
  return (
    <div className="my-2 flex flex-col gap-1.5">
      {data.title && (
        <h4 className="text-xs font-medium text-muted-foreground">{data.title}</h4>
      )}
      <div className="rounded-md border">
        <Table>
          <TableHeader>
            <TableRow>
              {data.columns.map((col) => (
                <TableHead key={col.key} className="text-xs">
                  {col.label}
                </TableHead>
              ))}
            </TableRow>
          </TableHeader>
          <TableBody>
            {data.rows.length === 0 ? (
              <TableRow>
                <TableCell
                  colSpan={data.columns.length}
                  className="h-12 text-center text-xs text-muted-foreground"
                >
                  No data
                </TableCell>
              </TableRow>
            ) : (
              data.rows.map((row, rowIdx) => (
                <TableRow key={rowIdx}>
                  {data.columns.map((col) => (
                    <TableCell key={col.key} className="text-xs">
                      {String(row[col.key] ?? "")}
                    </TableCell>
                  ))}
                </TableRow>
              ))
            )}
          </TableBody>
        </Table>
      </div>
    </div>
  );
}
