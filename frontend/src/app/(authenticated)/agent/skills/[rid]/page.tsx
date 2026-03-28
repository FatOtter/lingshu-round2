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

export default function AgentSkillDetailPage() {
  const params = useParams<{ rid: string }>();
  const router = useRouter();
  const queryClient = useQueryClient();
  const rid = params.rid;
  const isNew = rid === "new";

  const [apiName, setApiName] = useState("");
  const [displayName, setDisplayName] = useState("");
  const [description, setDescription] = useState("");
  const [systemPrompt, setSystemPrompt] = useState("");
  const [toolBindings, setToolBindings] = useState("[]");
  const [enabled, setEnabled] = useState(true);

  const { data: skill, isLoading } = useQuery({
    queryKey: ["copilot", "skill", rid],
    queryFn: () => copilotApi.getSkill(rid),
    enabled: !isNew,
  });

  useEffect(() => {
    if (skill?.data) {
      setApiName(skill.data.api_name);
      setDisplayName(skill.data.display_name);
      setDescription(skill.data.description ?? "");
      setSystemPrompt(skill.data.system_prompt);
      setToolBindings(JSON.stringify(skill.data.tool_bindings, null, 2));
      setEnabled(skill.data.enabled);
    }
  }, [skill]);

  const saveMutation = useMutation({
    mutationFn: () => {
      const payload = {
        api_name: apiName,
        display_name: displayName,
        description: description || null,
        system_prompt: systemPrompt,
        tool_bindings: JSON.parse(toolBindings),
        enabled,
      };
      return isNew
        ? copilotApi.registerSkill(payload)
        : copilotApi.updateSkill(rid, payload);
    },
    onSuccess: (res) => {
      queryClient.invalidateQueries({ queryKey: ["copilot", "skills"] });
      if (isNew && res?.data?.rid) {
        router.replace(`/agent/skills/${res.data.rid}`);
      }
    },
  });

  const deleteMutation = useMutation({
    mutationFn: () => copilotApi.deleteSkill(rid),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["copilot", "skills"] });
      router.push("/agent/skills");
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
            {isNew ? "New Skill" : displayName || apiName}
          </h1>
          {!isNew && (
            <Badge
              variant={enabled ? "default" : "secondary"}
              className="mt-1"
            >
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
            {isNew ? "Create" : "Save"}
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
            placeholder="e.g. summarizer"
          />
        </div>

        <div className="grid gap-1.5">
          <Label htmlFor="display_name">Display Name</Label>
          <Input
            id="display_name"
            value={displayName}
            onChange={(e) => setDisplayName(e.target.value)}
            placeholder="e.g. Text Summarizer"
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
          <Label htmlFor="system_prompt">System Prompt</Label>
          <Textarea
            id="system_prompt"
            value={systemPrompt}
            onChange={(e) => setSystemPrompt(e.target.value)}
            className="min-h-[160px] font-mono text-xs"
            placeholder="You are a specialized assistant that..."
          />
        </div>

        <div className="grid gap-1.5">
          <Label htmlFor="tool_bindings">Tool Bindings (JSON)</Label>
          <Textarea
            id="tool_bindings"
            value={toolBindings}
            onChange={(e) => setToolBindings(e.target.value)}
            className="min-h-[120px] font-mono text-xs"
            placeholder='[{"tool": "search", "config": {}}]'
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
                  ? "Skill is active and available"
                  : "Skill is disabled and will not be used"}
              </span>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
