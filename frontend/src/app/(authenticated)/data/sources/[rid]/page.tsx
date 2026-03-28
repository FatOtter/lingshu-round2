"use client";

import { useState, useEffect } from "react";
import { useParams, useRouter } from "next/navigation";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { dataApi } from "@/lib/api/data";
import { PageLoading } from "@/components/ui/loading";
import { Card, CardHeader, CardTitle, CardContent } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { Badge } from "@/components/ui/badge";
import { ConfirmDialog } from "@/components/ui/confirm-dialog";
import { Save, Trash2, Plug, ArrowLeft } from "lucide-react";

export default function ConnectionDetailPage() {
  const params = useParams<{ rid: string }>();
  const router = useRouter();
  const queryClient = useQueryClient();
  const rid = params.rid;
  const isNew = rid === "new";

  const [apiName, setApiName] = useState("");
  const [displayName, setDisplayName] = useState("");
  const [connectorType, setConnectorType] = useState("");
  const [configJson, setConfigJson] = useState("{}");
  const [deleteOpen, setDeleteOpen] = useState(false);

  const { data, isLoading } = useQuery({
    queryKey: ["data", "connections", rid],
    queryFn: () => dataApi.getConnection(rid),
    enabled: !isNew,
  });

  useEffect(() => {
    if (data?.data) {
      const conn = data.data;
      setApiName(conn.api_name);
      setDisplayName(conn.display_name);
      setConnectorType(conn.connector_type);
      setConfigJson(JSON.stringify(conn.config, null, 2));
    }
  }, [data]);

  const saveMutation = useMutation({
    mutationFn: () => {
      const payload = {
        api_name: apiName,
        display_name: displayName,
        connector_type: connectorType,
        config: JSON.parse(configJson),
      };
      return isNew
        ? dataApi.createConnection(payload)
        : dataApi.updateConnection(rid, payload);
    },
    onSuccess: (result) => {
      queryClient.invalidateQueries({ queryKey: ["data", "connections"] });
      if (isNew && result?.data?.rid) {
        router.replace(`/data/sources/${result.data.rid}`);
      }
    },
  });

  const deleteMutation = useMutation({
    mutationFn: () => dataApi.deleteConnection(rid),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["data", "connections"] });
      router.push("/data/sources");
    },
  });

  const testMutation = useMutation({
    mutationFn: () => dataApi.testConnection(rid),
  });

  if (isLoading && !isNew) {
    return <PageLoading />;
  }

  const isConfigValid = (() => {
    try {
      JSON.parse(configJson);
      return true;
    } catch {
      return false;
    }
  })();

  return (
    <div className="flex flex-col gap-4">
      <div className="flex items-center gap-2">
        <Button variant="ghost" size="icon" onClick={() => router.push("/data/sources")}>
          <ArrowLeft className="size-4" />
        </Button>
        <div>
          <h1 className="text-xl font-semibold">
            {isNew ? "New Connection" : displayName || "Connection Detail"}
          </h1>
          <p className="text-sm text-muted-foreground">
            {isNew ? "Create a new data connection" : `Edit connection ${rid}`}
          </p>
        </div>
      </div>

      <Card>
        <CardHeader>
          <CardTitle>Connection Settings</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="flex flex-col gap-4">
            <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
              <div className="flex flex-col gap-1.5">
                <Label htmlFor="api_name">API Name</Label>
                <Input
                  id="api_name"
                  value={apiName}
                  onChange={(e) => setApiName(e.target.value)}
                  placeholder="my_postgres_db"
                />
              </div>
              <div className="flex flex-col gap-1.5">
                <Label htmlFor="display_name">Display Name</Label>
                <Input
                  id="display_name"
                  value={displayName}
                  onChange={(e) => setDisplayName(e.target.value)}
                  placeholder="My Postgres Database"
                />
              </div>
            </div>

            <div className="flex flex-col gap-1.5">
              <Label htmlFor="connector_type">Connector Type</Label>
              <Input
                id="connector_type"
                value={connectorType}
                onChange={(e) => setConnectorType(e.target.value)}
                placeholder="postgres"
              />
            </div>

            <div className="flex flex-col gap-1.5">
              <Label htmlFor="config">Configuration (JSON)</Label>
              <Textarea
                id="config"
                value={configJson}
                onChange={(e) => setConfigJson(e.target.value)}
                className="min-h-32 font-mono text-xs"
                placeholder='{"host": "localhost", "port": 5432}'
              />
              {!isConfigValid && (
                <p className="text-xs text-destructive">Invalid JSON</p>
              )}
            </div>
          </div>
        </CardContent>
      </Card>

      <div className="flex items-center gap-2">
        <Button
          onClick={() => saveMutation.mutate()}
          disabled={saveMutation.isPending || !apiName || !connectorType || !isConfigValid}
        >
          <Save className="size-4" />
          {saveMutation.isPending ? "Saving..." : "Save"}
        </Button>

        {!isNew && (
          <>
            <Button
              variant="outline"
              onClick={() => testMutation.mutate()}
              disabled={testMutation.isPending}
            >
              <Plug className="size-4" />
              {testMutation.isPending ? "Testing..." : "Test Connection"}
            </Button>

            {testMutation.isSuccess && (
              <Badge variant={testMutation.data?.data?.success ? "default" : "destructive"}>
                {testMutation.data?.data?.success ? "Connected" : testMutation.data?.data?.message ?? "Failed"}
              </Badge>
            )}

            <div className="ml-auto">
              <Button variant="destructive" onClick={() => setDeleteOpen(true)}>
                <Trash2 className="size-4" />
                Delete
              </Button>
            </div>
          </>
        )}
      </div>

      {saveMutation.isError && (
        <p className="text-sm text-destructive">
          Failed to save: {saveMutation.error?.message ?? "Unknown error"}
        </p>
      )}

      <ConfirmDialog
        open={deleteOpen}
        onOpenChange={setDeleteOpen}
        title="Delete Connection"
        description="Are you sure you want to delete this connection? This action cannot be undone."
        confirmLabel="Delete"
        variant="destructive"
        onConfirm={() => deleteMutation.mutate()}
        loading={deleteMutation.isPending}
      />
    </div>
  );
}
