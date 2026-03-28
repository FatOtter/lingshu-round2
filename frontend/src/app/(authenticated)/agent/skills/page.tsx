"use client";

import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { useRouter } from "next/navigation";
import { copilotApi } from "@/lib/api/copilot";
import { DataTable, type ColumnDef } from "@/components/ui/data-table";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { PageLoading } from "@/components/ui/loading";
import { Plus } from "lucide-react";
import type { Skill } from "@/types/copilot";

const columns: ColumnDef<Skill>[] = [
  { key: "api_name", label: "API Name", sortable: true },
  { key: "display_name", label: "Display Name", sortable: true },
  {
    key: "enabled",
    label: "Enabled",
    render: (value) =>
      value ? (
        <Badge variant="default">Enabled</Badge>
      ) : (
        <Badge variant="secondary">Disabled</Badge>
      ),
  },
  {
    key: "created_at",
    label: "Created",
    sortable: true,
    render: (value) => {
      const date = value as string;
      return date ? new Date(date).toLocaleDateString() : "-";
    },
  },
];

export default function AgentSkillsPage() {
  const router = useRouter();
  const [page, setPage] = useState(1);
  const pageSize = 20;

  const { data, isLoading } = useQuery({
    queryKey: ["copilot", "skills", page],
    queryFn: () =>
      copilotApi.querySkills({ pagination: { page, page_size: pageSize } }),
  });

  if (isLoading && !data) {
    return <PageLoading />;
  }

  const skills = (data?.data ?? []) as unknown as Record<string, unknown>[];
  const total = data?.pagination?.total ?? 0;

  return (
    <div className="flex flex-col gap-4 p-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-xl font-semibold">Skills</h1>
          <p className="text-sm text-muted-foreground">Manage copilot skills and tool bindings</p>
        </div>
        <Button onClick={() => router.push("/agent/skills/new")}>
          <Plus className="size-4" />
          New Skill
        </Button>
      </div>

      <DataTable
        columns={columns}
        data={skills}
        total={total}
        page={page}
        pageSize={pageSize}
        onPageChange={setPage}
        loading={isLoading}
        onRowClick={(row) => router.push(`/agent/skills/${row.rid as string}`)}
      />
    </div>
  );
}
