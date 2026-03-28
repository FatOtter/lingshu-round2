"use client";

import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { copilotApi } from "@/lib/api/copilot";
import { DataTable, type ColumnDef } from "@/components/ui/data-table";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { PageLoading } from "@/components/ui/loading";
import type { Session } from "@/types/copilot";

const columns: ColumnDef<Session>[] = [
  { key: "session_id", label: "Session ID", sortable: true },
  {
    key: "mode",
    label: "Mode",
    render: (value) => (
      <Badge variant={value === "agent" ? "default" : "secondary"}>
        {value as string}
      </Badge>
    ),
  },
  {
    key: "status",
    label: "Status",
    render: (value) => (
      <Badge variant={value === "active" ? "default" : "outline"}>
        {value as string}
      </Badge>
    ),
  },
  { key: "title", label: "Title", sortable: true },
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

export default function AgentMonitorPage() {
  const [page, setPage] = useState(1);
  const [expanded, setExpanded] = useState<string | null>(null);
  const pageSize = 20;

  const { data, isLoading } = useQuery({
    queryKey: ["copilot", "monitor-sessions", page],
    queryFn: () =>
      copilotApi.querySessions({ pagination: { page, page_size: pageSize } }),
  });

  const { data: overview } = useQuery({
    queryKey: ["copilot", "overview"],
    queryFn: () => copilotApi.getOverview(),
  });

  if (isLoading && !data) return <PageLoading />;

  const sessions = (data?.data ?? []) as unknown as Record<string, unknown>[];
  const total = data?.pagination?.total ?? 0;
  const overviewData = overview?.data ?? {};
  const sessionStats = (overviewData.sessions ?? {}) as Record<string, unknown>;
  const modelStats = (overviewData.models ?? {}) as Record<string, unknown>;

  return (
    <div className="flex flex-col gap-4 p-6">
      <div>
        <h1 className="text-xl font-semibold">Monitor</h1>
        <p className="text-sm text-muted-foreground">View session activity and usage</p>
      </div>

      <div className="grid grid-cols-1 gap-4 sm:grid-cols-3">
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-medium text-muted-foreground">Total Sessions</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">{String(sessionStats.total ?? 0)}</div>
          </CardContent>
        </Card>
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-medium text-muted-foreground">Configured Models</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">{String(modelStats.total ?? 0)}</div>
          </CardContent>
        </Card>
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-medium text-muted-foreground">Current Page</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">{total} results</div>
          </CardContent>
        </Card>
      </div>

      <DataTable
        columns={columns}
        data={sessions}
        total={total}
        page={page}
        pageSize={pageSize}
        onPageChange={setPage}
        loading={isLoading}
        onRowClick={(row) => {
          const sid = row.session_id as string;
          setExpanded(expanded === sid ? null : sid);
        }}
      />

      {expanded && (
        <ExpandedSession sessionId={expanded} />
      )}
    </div>
  );
}

function ExpandedSession({ sessionId }: { sessionId: string }) {
  const { data, isLoading } = useQuery({
    queryKey: ["copilot", "session", sessionId],
    queryFn: () => copilotApi.getSession(sessionId),
  });

  if (isLoading) return <div className="p-4 text-sm text-muted-foreground">Loading session...</div>;

  const session = data?.data;
  if (!session) return null;

  return (
    <Card>
      <CardHeader className="pb-2">
        <CardTitle className="text-sm">Session: {session.session_id}</CardTitle>
      </CardHeader>
      <CardContent className="space-y-2 text-sm">
        <div><span className="font-medium">Mode:</span> {session.mode}</div>
        <div><span className="font-medium">Title:</span> {session.title ?? "Untitled"}</div>
        <div><span className="font-medium">Status:</span> {session.status}</div>
        <div><span className="font-medium">Created:</span> {new Date(session.created_at).toLocaleString()}</div>
        <div><span className="font-medium">Last Active:</span> {new Date(session.last_active_at).toLocaleString()}</div>
        {session.context && Object.keys(session.context).length > 0 && (
          <div>
            <span className="font-medium">Context:</span>
            <pre className="mt-1 rounded bg-muted p-2 text-xs">{JSON.stringify(session.context, null, 2)}</pre>
          </div>
        )}
      </CardContent>
    </Card>
  );
}
