"use client";

import { useState } from "react";
import { useParams } from "next/navigation";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { functionApi } from "@/lib/api/function";
import { PageLoading } from "@/components/ui/loading";
import { Card, CardHeader, CardTitle, CardDescription, CardContent } from "@/components/ui/card";
import { DataTable, type ColumnDef } from "@/components/ui/data-table";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Play, ShieldCheck } from "lucide-react";
import type { Execution, CapabilityDescriptor } from "@/types/function";

const SAFETY_LABEL: Record<string, string> = {
  SAFETY_READ_ONLY: "Read Only",
  SAFETY_IDEMPOTENT_WRITE: "Idempotent",
  SAFETY_NON_IDEMPOTENT: "Non-Idempotent",
  SAFETY_CRITICAL: "Critical",
};

const SAFETY_VARIANT: Record<string, "default" | "secondary" | "destructive" | "outline"> = {
  SAFETY_READ_ONLY: "secondary",
  SAFETY_IDEMPOTENT_WRITE: "default",
  SAFETY_NON_IDEMPOTENT: "outline",
  SAFETY_CRITICAL: "destructive",
};

const STATUS_VARIANT: Record<string, "default" | "secondary" | "destructive" | "outline"> = {
  completed: "default",
  running: "secondary",
  failed: "destructive",
  pending_confirmation: "outline",
  cancelled: "outline",
};

const historyColumns: ColumnDef<Execution>[] = [
  {
    key: "execution_id",
    label: "Execution ID",
    className: "max-w-[180px] truncate",
  },
  {
    key: "status",
    label: "Status",
    render: (value) => {
      const status = String(value);
      return <Badge variant={STATUS_VARIANT[status] ?? "outline"}>{status}</Badge>;
    },
  },
  {
    key: "started_at",
    label: "Started At",
    sortable: true,
    render: (value) => (value ? new Date(String(value)).toLocaleString() : "-"),
  },
  {
    key: "completed_at",
    label: "Completed At",
    render: (value) => (value ? new Date(String(value)).toLocaleString() : "-"),
  },
];

export default function ActionDetailPage() {
  const params = useParams<{ rid: string }>();
  const rid = params.rid;
  const queryClient = useQueryClient();

  const [paramValues, setParamValues] = useState<Record<string, string>>({});
  const [executionResult, setExecutionResult] = useState<Execution | null>(null);
  const [historyPage, setHistoryPage] = useState(1);
  const historyPageSize = 10;

  const { data: capabilitiesData, isLoading: loadingCap } = useQuery({
    queryKey: ["function", "capabilities", "action", rid],
    queryFn: () => functionApi.queryCapabilities({ type: "action" }),
  });

  const { data: historyData, isLoading: loadingHistory } = useQuery({
    queryKey: ["function", "executions", "action", rid, historyPage],
    queryFn: () =>
      functionApi.queryExecutions({
        capability_type: "action",
        pagination: { page: historyPage, page_size: historyPageSize },
      }),
  });

  const executeMutation = useMutation({
    mutationFn: (values: Record<string, unknown>) => functionApi.executeAction(rid, values),
    onSuccess: (response) => {
      setExecutionResult(response.data);
      queryClient.invalidateQueries({ queryKey: ["function", "executions"] });
    },
  });

  if (loadingCap) {
    return <PageLoading />;
  }

  const action: CapabilityDescriptor | undefined = capabilitiesData?.data?.find(
    (item: CapabilityDescriptor) => item.rid === rid,
  );

  const handleParamChange = (name: string, value: string) => {
    setParamValues((prev) => ({ ...prev, [name]: value }));
  };

  const handleExecute = () => {
    const parsedParams: Record<string, unknown> = {};
    for (const [key, value] of Object.entries(paramValues)) {
      try {
        parsedParams[key] = JSON.parse(value);
      } catch {
        parsedParams[key] = value;
      }
    }
    executeMutation.mutate(parsedParams);
  };

  const historyItems = (historyData?.data ?? []) as unknown as Record<string, unknown>[];
  const historyTotal = historyData?.pagination?.total ?? 0;

  return (
    <div className="flex flex-col gap-6">
      <div>
        <h1 className="text-xl font-semibold">{action?.display_name ?? rid}</h1>
        <p className="text-sm text-muted-foreground">Action execution</p>
      </div>

      {action && (
        <Card>
          <CardHeader>
            <div className="flex items-center gap-2">
              <ShieldCheck className="size-5 text-muted-foreground" />
              <CardTitle>Action Info</CardTitle>
            </div>
            <CardDescription>{action.description}</CardDescription>
          </CardHeader>
          <CardContent>
            <div className="flex flex-wrap gap-4 text-sm">
              <div>
                <span className="text-muted-foreground">API Name: </span>
                <span className="font-mono">{action.api_name}</span>
              </div>
              <div>
                <span className="text-muted-foreground">Safety Level: </span>
                <Badge variant={SAFETY_VARIANT[action.safety_level] ?? "outline"}>
                  {SAFETY_LABEL[action.safety_level] ?? action.safety_level}
                </Badge>
              </div>
            </div>
          </CardContent>
        </Card>
      )}

      <Card>
        <CardHeader>
          <CardTitle>Parameters</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="flex flex-col gap-4">
            {action?.parameters && action.parameters.length > 0 ? (
              action.parameters.map((param) => (
                <div key={param.name} className="flex flex-col gap-1.5">
                  <Label>
                    {param.name}
                    {param.required && <span className="text-destructive"> *</span>}
                    <span className="ml-2 text-xs text-muted-foreground">({param.type})</span>
                  </Label>
                  {param.description && (
                    <p className="text-xs text-muted-foreground">{param.description}</p>
                  )}
                  <Input
                    placeholder={`Enter ${param.name}`}
                    value={paramValues[param.name] ?? ""}
                    onChange={(e) => handleParamChange(param.name, e.target.value)}
                  />
                </div>
              ))
            ) : (
              <p className="text-sm text-muted-foreground">No parameters required</p>
            )}

            <Button
              onClick={handleExecute}
              disabled={executeMutation.isPending}
              className="w-fit"
            >
              <Play className="size-4" />
              {executeMutation.isPending ? "Executing..." : "Execute"}
            </Button>
          </div>
        </CardContent>
      </Card>

      {(executionResult || executeMutation.error) && (
        <Card>
          <CardHeader>
            <CardTitle>Execution Result</CardTitle>
          </CardHeader>
          <CardContent>
            {executeMutation.error ? (
              <div className="rounded-lg border border-destructive/50 bg-destructive/10 p-4 text-sm text-destructive">
                {executeMutation.error.message}
              </div>
            ) : executionResult ? (
              <div className="flex flex-col gap-3">
                <div className="flex flex-wrap gap-4 text-sm">
                  <div>
                    <span className="text-muted-foreground">Status: </span>
                    <Badge variant={STATUS_VARIANT[executionResult.status] ?? "outline"}>
                      {executionResult.status}
                    </Badge>
                  </div>
                  <div>
                    <span className="text-muted-foreground">ID: </span>
                    <span className="font-mono text-xs">{executionResult.execution_id}</span>
                  </div>
                </div>
                {executionResult.result && (
                  <pre className="max-h-64 overflow-auto rounded-lg bg-muted p-4 text-xs">
                    {JSON.stringify(executionResult.result, null, 2)}
                  </pre>
                )}
              </div>
            ) : null}
          </CardContent>
        </Card>
      )}

      <Card>
        <CardHeader>
          <CardTitle>Execution History</CardTitle>
        </CardHeader>
        <CardContent>
          <DataTable
            columns={historyColumns}
            data={historyItems as unknown as Record<string, unknown>[]}
            total={historyTotal}
            page={historyPage}
            pageSize={historyPageSize}
            onPageChange={setHistoryPage}
            loading={loadingHistory}
            emptyMessage="No execution history"
          />
        </CardContent>
      </Card>
    </div>
  );
}
