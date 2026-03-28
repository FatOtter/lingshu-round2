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
import { Save, Trash2, Power, PowerOff } from "lucide-react";

export default function AgentSubAgentDetailPage() {
  const params = useParams<{ rid: string }>();
  const router = useRouter();
  const queryClient = useQueryClient();
  const rid = params.rid;
  const isNew = rid === "new";

  const [apiName, setApiName] = useState("");
  const [displayName, setDisplayName] = useState("");
  const [description, setDescription] = useState("");
  const [modelRid, setModelRid] = useState("");
  const [systemPrompt, setSystemPrompt] = useState("");
  const [toolBindings, setToolBindings] = useState("[]");
  const [safetyPolicy, setSafetyPolicy] = useState("{}");
  const [enabled, setEnabled] = useState(true);

  const { data: agent, isLoading } = useQuery({
    queryKey: ["copilot", "sub-agent", rid],
    queryFn: () => copilotApi.getSubAgent(rid),
    enabled: !isNew,
  });

  useEffect(() => {
    if (agent?.data) {
      setApiName(agent.data.api_name);
      setDisplayName(agent.data.display_name);
      setDescription(agent.data.description ?? "");
      setModelRid(agent.data.model_rid ?? "");
      setSystemPrompt(agent.data.system_prompt ?? "");
      setToolBindings(JSON.stringify(agent.data.tool_bindings, null, 2));
      setSafetyPolicy(JSON.stringify(agent.data.safety_policy, null, 2));
      setEnabled(agent.data.enabled);
    }
  }, [agent]);

  const saveMutation = useMutation({
    mutationFn: () => {
      const payload = {
        api_name: apiName,
        display_name: displayName,
        description: description || null,
        model_rid: modelRid || null,
        system_prompt: systemPrompt || null,
        tool_bindings: JSON.parse(toolBindings),
        safety_policy: JSON.parse(safetyPolicy),
        enabled,
      };
      return isNew
        ? copilotApi.createSubAgent(payload)
        : copilotApi.updateSubAgent(rid, payload);
    },
    onSuccess: (res) => {
      queryClient.invalidateQueries({ queryKey: ["copilot", "sub-agents"] });
      if (isNew && res?.data?.rid) {
        router.replace(`/agent/sub-agents/${res.data.rid}`);
      }
    },
  });

  const deleteMutation = useMutation({
    mutationFn: () => copilotApi.deleteSubAgent(rid),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["copilot", "sub-agents"] });
      router.push("/agent/sub-agents");
    },
  });

  if (isLoading && !isNew) return <PageLoading />;

  return (
    <div className="flex flex-col gap-6 p-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-xl font-semibold">
            {isNew ? "New Sub-Agent" : displayName || apiName}
          </h1>
          {!isNew && (
            <Badge variant={enabled ? "default" : "secondary"} className="mt-1">
              {enabled ? <><Power className="mr-1 size-3" />Enabled</> : <><PowerOff className="mr-1 size-3" />Disabled</>}
            </Badge>
          )}
        </div>
        <div className="flex gap-2">
          {!isNew && (
            <Button variant="outline" onClick={() => deleteMutation.mutate()} disabled={deleteMutation.isPending}>
              <Trash2 className="size-4" />Delete
            </Button>
          )}
          <Button onClick={() => saveMutation.mutate()} disabled={saveMutation.isPending}>
            <Save className="size-4" />{isNew ? "Create" : "Save"}
          </Button>
        </div>
      </div>
      <Separator />
      <div className="grid max-w-xl gap-4">
        <div className="grid gap-1.5">
          <Label htmlFor="api_name">API Name</Label>
          <Input id="api_name" value={apiName} onChange={(e) => setApiName(e.target.value)} placeholder="e.g. researcher" />
        </div>
        <div className="grid gap-1.5">
          <Label htmlFor="display_name">Display Name</Label>
          <Input id="display_name" value={displayName} onChange={(e) => setDisplayName(e.target.value)} placeholder="e.g. Research Agent" />
        </div>
        <div className="grid gap-1.5">
          <Label htmlFor="description">Description</Label>
          <Input id="description" value={description} onChange={(e) => setDescription(e.target.value)} placeholder="Optional description" />
        </div>
        <div className="grid gap-1.5">
          <Label htmlFor="model_rid">Model RID</Label>
          <Input id="model_rid" value={modelRid} onChange={(e) => setModelRid(e.target.value)} placeholder="e.g. ri.model.abc123" />
        </div>
        <div className="grid gap-1.5">
          <Label htmlFor="system_prompt">System Prompt</Label>
          <Textarea id="system_prompt" value={systemPrompt} onChange={(e) => setSystemPrompt(e.target.value)} className="min-h-[160px] font-mono text-xs" placeholder="You are a specialized assistant that..." />
        </div>
        <div className="grid gap-1.5">
          <Label htmlFor="tool_bindings">Tool Bindings (JSON)</Label>
          <Textarea id="tool_bindings" value={toolBindings} onChange={(e) => setToolBindings(e.target.value)} className="min-h-[120px] font-mono text-xs" placeholder='[{"tool": "search", "config": {}}]' />
        </div>
        <div className="grid gap-1.5">
          <Label htmlFor="safety_policy">Safety Policy (JSON)</Label>
          <Textarea id="safety_policy" value={safetyPolicy} onChange={(e) => setSafetyPolicy(e.target.value)} className="min-h-[80px] font-mono text-xs" placeholder='{"max_iterations": 10}' />
        </div>
        {!isNew && (
          <div className="grid gap-1.5">
            <Label htmlFor="enabled">Enabled</Label>
            <div className="flex items-center gap-2">
              <Button variant={enabled ? "default" : "outline"} size="sm" onClick={() => setEnabled(!enabled)}>
                {enabled ? "Enabled" : "Disabled"}
              </Button>
              <span className="text-sm text-muted-foreground">
                {enabled ? "Sub-agent is active and available" : "Sub-agent is disabled and will not be used"}
              </span>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
