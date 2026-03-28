"use client";

import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { useRouter } from "next/navigation";
import { copilotApi } from "@/lib/api/copilot";
import { DataTable, type ColumnDef } from "@/components/ui/data-table";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { PageLoading } from "@/components/ui/loading";
import { Trash2 } from "lucide-react";
import type { Session } from "@/types/copilot";

const columns: ColumnDef<Session>[] = [
  {
    key: "title",
    label: "Title",
    sortable: true,
    render: (value) => (value as string) ?? "Untitled",
  },
  {
    key: "mode",
    label: "Mode",
    render: (value) => {
      const mode = value as string;
      return (
        <Badge variant={mode === "agent" ? "default" : "secondary"}>
          {mode}
        </Badge>
      );
    },
  },
  {
    key: "status",
    label: "Status",
    render: (value) => {
      const status = value as string;
      return (
        <Badge variant={status === "active" ? "default" : "outline"}>
          {status}
        </Badge>
      );
    },
  },
  {
    key: "created_at",
    label: "Created",
    sortable: true,
    render: (value) => {
      const date = value as string;
      return date ? new Date(date).toLocaleString() : "-";
    },
  },
  {
    key: "last_active_at",
    label: "Last Active",
    sortable: true,
    render: (value) => {
      const date = value as string;
      return date ? new Date(date).toLocaleString() : "-";
    },
  },
];

export default function AgentSessionsPage() {
  const router = useRouter();
  const queryClient = useQueryClient();
  const [page, setPage] = useState(1);
  const pageSize = 20;

  const { data, isLoading } = useQuery({
    queryKey: ["copilot", "sessions", page],
    queryFn: () =>
      copilotApi.querySessions({ pagination: { page, page_size: pageSize } }),
  });

  const deleteMutation = useMutation({
    mutationFn: (sessionId: string) => copilotApi.deleteSession(sessionId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["copilot", "sessions"] });
    },
  });

  if (isLoading && !data) {
    return <PageLoading />;
  }

  const sessions = (data?.data ?? []) as unknown as Record<string, unknown>[];
  const total = data?.pagination?.total ?? 0;

  return (
    <div className="flex flex-col gap-4 p-6">
      <div>
        <h1 className="text-xl font-semibold">Sessions</h1>
        <p className="text-sm text-muted-foreground">Manage agent conversation sessions</p>
      </div>

      <DataTable
        columns={[
          ...columns,
          {
            key: "_actions",
            label: "",
            className: "w-10",
            render: (_value, row) => (
              <Button
                variant="ghost"
                size="icon-xs"
                onClick={(e) => {
                  e.stopPropagation();
                  deleteMutation.mutate(row.session_id as string);
                }}
              >
                <Trash2 className="size-3.5 text-muted-foreground" />
              </Button>
            ),
          },
        ] as ColumnDef<Record<string, unknown>>[]}
        data={sessions}
        total={total}
        page={page}
        pageSize={pageSize}
        onPageChange={setPage}
        loading={isLoading}
        onRowClick={(row) =>
          router.push(`/agent/chat/${row.session_id as string}`)
        }
      />
    </div>
  );
}
