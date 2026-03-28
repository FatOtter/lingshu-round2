"use client";

import { useEffect, useState } from "react";
import { useParams, useRouter } from "next/navigation";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { copilotApi } from "@/lib/api/copilot";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { Badge } from "@/components/ui/badge";
import { Separator } from "@/components/ui/separator";
import { PageLoading } from "@/components/ui/loading";
import { Save, Trash2, Power, PowerOff, Wifi, Search } from "lucide-react";

export default function AgentMcpDetailPage() {
  const params = useParams<{ rid: string }>();
  const router = useRouter();
  const queryClient = useQueryClient();
  const rid = params.rid;
  const isNew = rid === "new";

  const [apiName, setApiName] = useState("");
  const [displayName, setDisplayName] = useState("");
  const [description, setDescription] = useState("");
  const [transport, setTransport] = useState("{}");
  const [auth, setAuth] = useState("null");
  const [enabled, setEnabled] = useState(true);

  const { data: connection, isLoading } = useQuery({
    queryKey: ["copilot", "mcp", rid],
    queryFn: () => copilotApi.getMcp(rid),
    enabled: !isNew,
  });

  useEffect(() => {
    if (connection?.data) {
      setApiName(connection.data.api_name);
      setDisplayName(connection.data.display_name);
      setDescription(connection.data.description ?? "");
      setTransport(JSON.stringify(connection.data.transport, null, 2));
      setAuth(
        connection.data.auth
          ? JSON.stringify(connection.data.auth, null, 2)
          : "null"
      );
      setEnabled(connection.data.enabled);
    }
  }, [connection]);

  const saveMutation = useMutation({
    mutationFn: () => {
      const parsedAuth = JSON.parse(auth);
      const payload = {
        api_name: apiName,
        display_name: displayName,
        description: description || null,
        transport: JSON.parse(transport),
        auth: parsedAuth === null ? undefined : parsedAuth,
        enabled,
      };
      return isNew
        ? copilotApi.connectMcp(payload)
        : copilotApi.updateMcp(rid, payload);
    },
    onSuccess: (res) => {
      queryClient.invalidateQueries({ queryKey: ["copilot", "mcp"] });
      if (isNew && res?.data?.rid) {
        router.replace(`/agent/mcp/${res.data.rid}`);
      }
    },
  });

  const deleteMutation = useMutation({
    mutationFn: () => copilotApi.deleteMcp(rid),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["copilot", "mcp"] });
      router.push("/agent/mcp");
    },
  });

  const [testResult, setTestResult] = useState<Record<string, unknown> | null>(null);

  const testMutation = useMutation({
    mutationFn: () => copilotApi.testConnection(rid),
    onSuccess: (res) => {
      setTestResult(res?.data ?? null);
    },
  });

  const [discoveredTools, setDiscoveredTools] = useState<Record<string, unknown>[] | null>(null);

  const discoverMutation = useMutation({
    mutationFn: () => copilotApi.discoverTools(rid),
    onSuccess: (res) => {
      setDiscoveredTools(res?.data ?? []);
    },
  });

  if (isLoading && !isNew) {
    return <PageLoading />;
  }

  const status = connection?.data?.status ?? "disconnected";
  const storedDiscoveredTools = connection?.data?.discovered_tools ?? [];

  return (
    <div className="flex flex-col gap-6 p-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-xl font-semibold">
            {isNew ? "New MCP Connection" : displayName || apiName}
          </h1>
          {!isNew && (
            <div className="mt-1 flex gap-2">
              <Badge variant={status === "connected" ? "default" : "secondary"}>
                {status}
              </Badge>
              <Badge variant={enabled ? "default" : "secondary"}>
                {enabled ? (
                  <>
                    <Power className="mr-1 size-3" />
                    Enabled
                  </>
                ) : (
                  <>
                    <PowerOff className="mr-1 size-3" />
                    Disabled
                  </>
                )}
              </Badge>
            </div>
          )}
        </div>
        <div className="flex gap-2">
          {!isNew && (
            <>
              <Button
                variant="outline"
                onClick={() => testMutation.mutate()}
                disabled={testMutation.isPending}
              >
                <Wifi className="size-4" />
                Test Connection
              </Button>
              <Button
                variant="outline"
                onClick={() => discoverMutation.mutate()}
                disabled={discoverMutation.isPending}
              >
                <Search className="size-4" />
                Discover Tools
              </Button>
              <Button
                variant="outline"
                onClick={() => deleteMutation.mutate()}
                disabled={deleteMutation.isPending}
              >
                <Trash2 className="size-4" />
                Delete
              </Button>
            </>
          )}
          <Button
            onClick={() => saveMutation.mutate()}
            disabled={saveMutation.isPending}
          >
            <Save className="size-4" />
            {isNew ? "Connect" : "Save"}
          </Button>
        </div>
      </div>

      <Separator />

      <div className="grid max-w-xl gap-4">
        <div className="grid gap-1.5">
          <Label htmlFor="api_name">API Name</Label>
          <Input
            id="api_name"
            value={apiName}
            onChange={(e) => setApiName(e.target.value)}
            placeholder="e.g. my-mcp-server"
          />
        </div>

        <div className="grid gap-1.5">
          <Label htmlFor="display_name">Display Name</Label>
          <Input
            id="display_name"
            value={displayName}
            onChange={(e) => setDisplayName(e.target.value)}
            placeholder="e.g. My MCP Server"
          />
        </div>

        <div className="grid gap-1.5">
          <Label htmlFor="description">Description</Label>
          <Input
            id="description"
            value={description}
            onChange={(e) => setDescription(e.target.value)}
            placeholder="Optional description"
          />
        </div>

        <div className="grid gap-1.5">
          <Label htmlFor="transport">Transport Config (JSON)</Label>
          <Textarea
            id="transport"
            value={transport}
            onChange={(e) => setTransport(e.target.value)}
            className="min-h-[120px] font-mono text-xs"
            placeholder='{"type": "stdio", "command": "mcp-server"}'
          />
        </div>

        <div className="grid gap-1.5">
          <Label htmlFor="auth">Auth Config (JSON, null if none)</Label>
          <Textarea
            id="auth"
            value={auth}
            onChange={(e) => setAuth(e.target.value)}
            className="min-h-[100px] font-mono text-xs"
            placeholder='{"token": "..."} or null'
          />
        </div>

        {!isNew && (
          <div className="grid gap-1.5">
            <Label htmlFor="enabled">Enabled</Label>
            <div className="flex items-center gap-2">
              <Button
                variant={enabled ? "default" : "outline"}
                size="sm"
                onClick={() => setEnabled(!enabled)}
              >
                {enabled ? "Enabled" : "Disabled"}
              </Button>
              <span className="text-sm text-muted-foreground">
                {enabled
                  ? "Connection is active"
                  : "Connection is disabled"}
              </span>
            </div>
          </div>
        )}
      </div>

      {/* Test Connection Result */}
      {testResult && (
        <>
          <Separator />
          <div className="grid max-w-xl gap-2">
            <h2 className="text-lg font-medium">Test Result</h2>
            <pre className="rounded-md bg-muted p-3 font-mono text-xs">
              {JSON.stringify(testResult, null, 2)}
            </pre>
          </div>
        </>
      )}

      {/* Discovered Tools */}
      {!isNew && (
        <>
          <Separator />
          <div className="grid max-w-xl gap-2">
            <h2 className="text-lg font-medium">Discovered Tools</h2>
            {(discoveredTools ?? storedDiscoveredTools).length > 0 ? (
              <pre className="rounded-md bg-muted p-3 font-mono text-xs">
                {JSON.stringify(discoveredTools ?? storedDiscoveredTools, null, 2)}
              </pre>
            ) : (
              <p className="text-sm text-muted-foreground">
                No tools discovered yet. Click &quot;Discover Tools&quot; to scan the MCP server.
              </p>
            )}
          </div>
        </>
      )}
    </div>
  );
}
