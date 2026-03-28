"use client";

import { useState, useEffect } from "react";
import { useParams } from "next/navigation";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { functionApi } from "@/lib/api/function";
import { PageLoading } from "@/components/ui/loading";
import { Card, CardHeader, CardTitle, CardContent } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { Label } from "@/components/ui/label";
import { Badge } from "@/components/ui/badge";
import { Save, Play } from "lucide-react";
import type { Execution } from "@/types/function";

const STATUS_VARIANT: Record<string, "default" | "secondary" | "destructive" | "outline"> = {
  completed: "default",
  running: "secondary",
  failed: "destructive",
  pending_confirmation: "outline",
  cancelled: "outline",
};

export default function GlobalFunctionDetailPage() {
  const params = useParams<{ rid: string }>();
  const rid = params.rid;
  const queryClient = useQueryClient();

  const [apiName, setApiName] = useState("");
  const [displayName, setDisplayName] = useState("");
  const [description, setDescription] = useState("");
  const [parametersJson, setParametersJson] = useState("");
  const [implementationJson, setImplementationJson] = useState("");
  const [testParamsJson, setTestParamsJson] = useState("{}");
  const [executeResult, setExecuteResult] = useState<Execution | null>(null);

  const { data, isLoading } = useQuery({
    queryKey: ["function", "globals", rid],
    queryFn: () => functionApi.getFunction(rid),
  });

  useEffect(() => {
    if (data?.data) {
      const fn = data.data;
      setApiName(fn.api_name);
      setDisplayName(fn.display_name);
      setDescription(fn.description);
      setParametersJson(JSON.stringify(fn.parameters, null, 2));
      setImplementationJson(JSON.stringify(fn.implementation, null, 2));
    }
  }, [data]);

  const saveMutation = useMutation({
    mutationFn: () => {
      let parsedParams: Record<string, unknown> = {};
      let parsedImpl: Record<string, unknown> = {};
      try {
        parsedParams = JSON.parse(parametersJson);
      } catch {
        throw new Error("Invalid JSON in parameters");
      }
      try {
        parsedImpl = JSON.parse(implementationJson);
      } catch {
        throw new Error("Invalid JSON in implementation");
      }
      return functionApi.updateFunction(rid, {
        api_name: apiName,
        display_name: displayName,
        description,
        parameters: parsedParams,
        implementation: parsedImpl,
      });
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["function", "globals", rid] });
    },
  });

  const executeMutation = useMutation({
    mutationFn: () => {
      let parsedTestParams: Record<string, unknown> = {};
      try {
        parsedTestParams = JSON.parse(testParamsJson);
      } catch {
        throw new Error("Invalid JSON in test parameters");
      }
      return functionApi.executeFunction(rid, parsedTestParams);
    },
    onSuccess: (response) => {
      setExecuteResult(response.data);
    },
  });

  if (isLoading) {
    return <PageLoading />;
  }

  return (
    <div className="flex flex-col gap-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-xl font-semibold">{displayName || rid}</h1>
          <p className="text-sm text-muted-foreground">Global function detail</p>
        </div>
        <div className="flex items-center gap-2">
          <Button
            variant="outline"
            onClick={() => executeMutation.mutate()}
            disabled={executeMutation.isPending}
          >
            <Play className="size-4" />
            {executeMutation.isPending ? "Running..." : "Execute"}
          </Button>
          <Button onClick={() => saveMutation.mutate()} disabled={saveMutation.isPending}>
            <Save className="size-4" />
            {saveMutation.isPending ? "Saving..." : "Save"}
          </Button>
        </div>
      </div>

      {saveMutation.error && (
        <div className="rounded-lg border border-destructive/50 bg-destructive/10 p-3 text-sm text-destructive">
          {saveMutation.error.message}
        </div>
      )}

      {saveMutation.isSuccess && (
        <div className="rounded-lg border border-green-500/50 bg-green-500/10 p-3 text-sm text-green-700 dark:text-green-400">
          Function saved successfully.
        </div>
      )}

      <Card>
        <CardHeader>
          <CardTitle>Details</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="flex flex-col gap-4">
            <div className="flex flex-col gap-1.5">
              <Label htmlFor="api_name">API Name</Label>
              <Input
                id="api_name"
                value={apiName}
                onChange={(e) => setApiName(e.target.value)}
                placeholder="e.g. my_function"
              />
            </div>

            <div className="flex flex-col gap-1.5">
              <Label htmlFor="display_name">Display Name</Label>
              <Input
                id="display_name"
                value={displayName}
                onChange={(e) => setDisplayName(e.target.value)}
                placeholder="e.g. My Function"
              />
            </div>

            <div className="flex flex-col gap-1.5">
              <Label htmlFor="description">Description</Label>
              <Textarea
                id="description"
                value={description}
                onChange={(e) => setDescription(e.target.value)}
                placeholder="Describe what this function does..."
              />
            </div>

            <div className="flex flex-col gap-1.5">
              <Label htmlFor="parameters">Parameters (JSON)</Label>
              <Textarea
                id="parameters"
                value={parametersJson}
                onChange={(e) => setParametersJson(e.target.value)}
                className="font-mono text-xs"
                rows={6}
              />
            </div>

            <div className="flex flex-col gap-1.5">
              <Label htmlFor="implementation">Implementation (JSON)</Label>
              <Textarea
                id="implementation"
                value={implementationJson}
                onChange={(e) => setImplementationJson(e.target.value)}
                className="font-mono text-xs"
                rows={8}
              />
            </div>
          </div>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Test Execution</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="flex flex-col gap-4">
            <div className="flex flex-col gap-1.5">
              <Label htmlFor="test_params">Test Parameters (JSON)</Label>
              <Textarea
                id="test_params"
                value={testParamsJson}
                onChange={(e) => setTestParamsJson(e.target.value)}
                className="font-mono text-xs"
                rows={4}
              />
            </div>

            <Button
              variant="outline"
              onClick={() => executeMutation.mutate()}
              disabled={executeMutation.isPending}
              className="w-fit"
            >
              <Play className="size-4" />
              {executeMutation.isPending ? "Running..." : "Execute Test"}
            </Button>

            {executeMutation.error && (
              <div className="rounded-lg border border-destructive/50 bg-destructive/10 p-3 text-sm text-destructive">
                {executeMutation.error.message}
              </div>
            )}

            {executeResult && (
              <div className="flex flex-col gap-3">
                <div className="flex items-center gap-3 text-sm">
                  <span className="text-muted-foreground">Status:</span>
                  <Badge variant={STATUS_VARIANT[executeResult.status] ?? "outline"}>
                    {executeResult.status}
                  </Badge>
                  <span className="text-muted-foreground">ID:</span>
                  <span className="font-mono text-xs">{executeResult.execution_id}</span>
                </div>
                {executeResult.result && (
                  <pre className="max-h-64 overflow-auto rounded-lg bg-muted p-4 text-xs">
                    {JSON.stringify(executeResult.result, null, 2)}
                  </pre>
                )}
              </div>
            )}
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
