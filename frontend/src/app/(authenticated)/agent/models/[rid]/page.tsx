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
import { Save, Trash2, Star } from "lucide-react";

export default function AgentModelDetailPage() {
  const params = useParams<{ rid: string }>();
  const router = useRouter();
  const queryClient = useQueryClient();
  const rid = params.rid;
  const isNew = rid === "new";

  const [apiName, setApiName] = useState("");
  const [displayName, setDisplayName] = useState("");
  const [provider, setProvider] = useState("");
  const [connection, setConnection] = useState("{}");
  const [parameters, setParameters] = useState("{}");

  const { data: model, isLoading } = useQuery({
    queryKey: ["copilot", "model", rid],
    queryFn: () => copilotApi.getModel(rid),
    enabled: !isNew,
  });

  useEffect(() => {
    if (model?.data) {
      setApiName(model.data.api_name);
      setDisplayName(model.data.display_name);
      setProvider(model.data.provider);
      setConnection(JSON.stringify(model.data.connection, null, 2));
      setParameters(JSON.stringify(model.data.parameters, null, 2));
    }
  }, [model]);

  const saveMutation = useMutation({
    mutationFn: () => {
      const payload = {
        api_name: apiName,
        display_name: displayName,
        provider,
        connection: JSON.parse(connection),
        parameters: JSON.parse(parameters),
      };
      return isNew
        ? copilotApi.registerModel(payload)
        : copilotApi.updateModel(rid, payload);
    },
    onSuccess: (res) => {
      queryClient.invalidateQueries({ queryKey: ["copilot", "models"] });
      if (isNew && res?.data?.rid) {
        router.replace(`/agent/models/${res.data.rid}`);
      }
    },
  });

  const deleteMutation = useMutation({
    mutationFn: () => copilotApi.deleteModel(rid),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["copilot", "models"] });
      router.push("/agent/models");
    },
  });

  if (isLoading && !isNew) {
    return <PageLoading />;
  }

  return (
    <div className="flex flex-col gap-6 p-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-xl font-semibold">
            {isNew ? "Register Model" : displayName || apiName}
          </h1>
          {!isNew && model?.data?.is_default && (
            <Badge variant="default" className="mt-1">
              <Star className="mr-1 size-3" />
              Default Model
            </Badge>
          )}
        </div>
        <div className="flex gap-2">
          {!isNew && (
            <Button
              variant="outline"
              onClick={() => deleteMutation.mutate()}
              disabled={deleteMutation.isPending}
            >
              <Trash2 className="size-4" />
              Delete
            </Button>
          )}
          <Button
            onClick={() => saveMutation.mutate()}
            disabled={saveMutation.isPending}
          >
            <Save className="size-4" />
            {isNew ? "Register" : "Save"}
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
            placeholder="e.g. gpt-4o"
          />
        </div>

        <div className="grid gap-1.5">
          <Label htmlFor="display_name">Display Name</Label>
          <Input
            id="display_name"
            value={displayName}
            onChange={(e) => setDisplayName(e.target.value)}
            placeholder="e.g. GPT-4o"
          />
        </div>

        <div className="grid gap-1.5">
          <Label htmlFor="provider">Provider</Label>
          <Input
            id="provider"
            value={provider}
            onChange={(e) => setProvider(e.target.value)}
            placeholder="e.g. openai"
          />
        </div>

        <div className="grid gap-1.5">
          <Label htmlFor="connection">Connection Config (JSON)</Label>
          <Textarea
            id="connection"
            value={connection}
            onChange={(e) => setConnection(e.target.value)}
            className="min-h-[120px] font-mono text-xs"
            placeholder='{"api_key": "...", "base_url": "..."}'
          />
        </div>

        <div className="grid gap-1.5">
          <Label htmlFor="parameters">Parameters (JSON)</Label>
          <Textarea
            id="parameters"
            value={parameters}
            onChange={(e) => setParameters(e.target.value)}
            className="min-h-[120px] font-mono text-xs"
            placeholder='{"temperature": 0.7, "max_tokens": 4096}'
          />
        </div>
      </div>
    </div>
  );
}
