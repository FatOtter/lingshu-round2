"use client";

import { useState, useCallback } from "react";
import { useParams, useRouter } from "next/navigation";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { ontologyApi } from "@/lib/api/ontology";
import { PageLoading } from "@/components/ui/loading";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { Label } from "@/components/ui/label";
import { Tabs, TabsList, TabsTrigger, TabsContent } from "@/components/ui/tabs";
import { Card, CardHeader, CardTitle, CardContent } from "@/components/ui/card";
import { ConfirmDialog } from "@/components/ui/confirm-dialog";
import { ExecutionConfigEditor } from "@/components/ontology/execution-config-editor";
import { Save, Code, Settings, Trash2, Upload } from "lucide-react";
import { ApiClientError } from "@/lib/api/client";

export default function ActionTypeEditorPage() {
  const params = useParams();
  const router = useRouter();
  const rid = params.rid as string;
  const queryClient = useQueryClient();

  const isNew = rid === "new";

  const { data, isLoading } = useQuery({
    queryKey: ["ontology", "action-type", rid],
    queryFn: () => ontologyApi.getActionTypeDraft(rid),
    enabled: !isNew,
  });

  const actionType = data?.data;

  const [apiName, setApiName] = useState("");
  const [displayName, setDisplayName] = useState("");
  const [description, setDescription] = useState("");
  const [operatesOnRid, setOperatesOnRid] = useState("");
  const [safetyLevel, setSafetyLevel] = useState("");
  const [initialized, setInitialized] = useState(false);
  const [deleteOpen, setDeleteOpen] = useState(false);
  const [deleteError, setDeleteError] = useState<string | null>(null);

  if (!isNew && actionType && !initialized) {
    setApiName(actionType.api_name);
    setDisplayName(actionType.display_name);
    setDescription(actionType.description);
    setOperatesOnRid(actionType.operates_on_rid);
    setSafetyLevel(actionType.safety_level);
    setInitialized(true);
  }

  const [saveError, setSaveError] = useState<string | null>(null);

  const saveMutation = useMutation({
    mutationFn: () => {
      setSaveError(null);
      const payload = {
        api_name: apiName,
        display_name: displayName,
        description,
        operates_on_rid: operatesOnRid,
        safety_level: safetyLevel,
      };
      if (isNew) {
        return ontologyApi.createActionType(payload);
      }
      return ontologyApi.updateActionType(rid, payload);
    },
    onSuccess: (result) => {
      queryClient.invalidateQueries({ queryKey: ["ontology", "action-type", rid] });
      queryClient.invalidateQueries({ queryKey: ["ontology", "action-types"] });
      if (isNew && result?.data?.rid) {
        router.push(`/ontology/action-types/${result.data.rid}`);
      }
    },
    onError: (err) => {
      const message = err instanceof ApiClientError
        ? `${err.code}: ${err.message}`
        : "Failed to save action type";
      setSaveError(message);
    },
  });

  const submitToStagingMutation = useMutation({
    mutationFn: () => ontologyApi.submitToStaging("action-types", rid),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["ontology", "action-type", rid] });
      queryClient.invalidateQueries({ queryKey: ["ontology", "action-types"] });
    },
    onError: (err) => {
      const message = err instanceof ApiClientError
        ? `${err.code}: ${err.message}`
        : "Failed to submit to staging";
      setSaveError(message);
    },
  });

  const deleteMutation = useMutation({
    mutationFn: async () => {
      await ontologyApi.acquireLock("action-types", rid);
      try {
        await ontologyApi.deleteActionType(rid);
      } catch (err) {
        await ontologyApi.releaseLock("action-types", rid).catch(() => {});
        throw err;
      }
    },
    onSuccess: () => {
      setDeleteOpen(false);
      queryClient.invalidateQueries({ queryKey: ["ontology", "action-types"] });
      router.push("/ontology/action-types");
    },
    onError: (err) => {
      const message = err instanceof ApiClientError
        ? `${err.code}: ${err.message}`
        : "Failed to delete action type";
      setDeleteError(message);
    },
  });

  const handleSaveExecution = useCallback(
    (executionConfig: Record<string, unknown>) => {
      return ontologyApi.updateActionType(rid, { execution: executionConfig }).then(() => {
        queryClient.invalidateQueries({ queryKey: ["ontology", "action-type", rid] });
      });
    },
    [rid, queryClient],
  );

  if (isLoading && !isNew) {
    return <PageLoading />;
  }

  return (
    <div className="flex flex-col gap-4">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-xl font-semibold">
            {isNew ? "New Action Type" : actionType?.display_name ?? rid}
          </h1>
          {!isNew && actionType && (
            <p className="text-sm text-muted-foreground">{actionType.api_name}</p>
          )}
        </div>
        <div className="flex items-center gap-2">
          {!isNew && actionType?.version_status === "draft" && (
            <Button
              variant="outline"
              onClick={() => submitToStagingMutation.mutate()}
              disabled={submitToStagingMutation.isPending}
            >
              <Upload className="size-4" />
              {submitToStagingMutation.isPending ? "Submitting..." : "Submit to Staging"}
            </Button>
          )}
          {!isNew && (
            <Button
              variant="destructive"
              onClick={() => { setDeleteError(null); setDeleteOpen(true); }}
            >
              <Trash2 className="size-4" />
              Delete
            </Button>
          )}
          <Button onClick={() => saveMutation.mutate()} disabled={saveMutation.isPending}>
            <Save className="size-4" />
            {saveMutation.isPending ? "Saving..." : "Save"}
          </Button>
        </div>
      </div>

      {saveError && (
        <div className="rounded-md border border-red-200 bg-red-50 p-3 text-sm text-red-700">
          {saveError}
        </div>
      )}

      <Tabs defaultValue="info">
        <TabsList>
          <TabsTrigger value="info">Info</TabsTrigger>
          <TabsTrigger value="parameters">Parameters</TabsTrigger>
          <TabsTrigger value="execution">Execution Config</TabsTrigger>
        </TabsList>

        <TabsContent value="info">
          <div className="mt-4 grid max-w-xl gap-4">
            <div className="grid gap-1.5">
              <Label htmlFor="api_name">API Name</Label>
              <Input
                id="api_name"
                value={apiName}
                onChange={(e) => setApiName(e.target.value)}
                placeholder="e.g. my_action_type"
              />
            </div>
            <div className="grid gap-1.5">
              <Label htmlFor="display_name">Display Name</Label>
              <Input
                id="display_name"
                value={displayName}
                onChange={(e) => setDisplayName(e.target.value)}
                placeholder="e.g. My Action Type"
              />
            </div>
            <div className="grid gap-1.5">
              <Label htmlFor="description">Description</Label>
              <Textarea
                id="description"
                value={description}
                onChange={(e) => setDescription(e.target.value)}
                placeholder="Describe this action type..."
              />
            </div>
            <div className="grid gap-1.5">
              <Label htmlFor="operates_on_rid">Operates On (Object Type RID)</Label>
              <Input
                id="operates_on_rid"
                value={operatesOnRid}
                onChange={(e) => setOperatesOnRid(e.target.value)}
                placeholder="e.g. ri.ontology.main.object-type.xxx"
              />
            </div>
            <div className="grid gap-1.5">
              <Label htmlFor="safety_level">Safety Level</Label>
              <Input
                id="safety_level"
                value={safetyLevel}
                onChange={(e) => setSafetyLevel(e.target.value)}
                placeholder="e.g. SAFE, UNSAFE, CRITICAL"
              />
            </div>
          </div>
        </TabsContent>

        <TabsContent value="parameters">
          <div className="mt-4">
            <Card>
              <CardHeader>
                <div className="flex items-center gap-2">
                  <Settings className="size-5 text-muted-foreground" />
                  <CardTitle>Parameters</CardTitle>
                </div>
              </CardHeader>
              <CardContent>
                {actionType?.parameters && actionType.parameters.length > 0 ? (
                  <pre className="rounded-lg bg-muted p-4 text-xs overflow-auto">
                    {JSON.stringify(actionType.parameters, null, 2)}
                  </pre>
                ) : (
                  <p className="text-sm text-muted-foreground">No parameters defined</p>
                )}
              </CardContent>
            </Card>
          </div>
        </TabsContent>

        <TabsContent value="execution">
          <div className="mt-4">
            <Card>
              <CardHeader>
                <div className="flex items-center gap-2">
                  <Code className="size-5 text-muted-foreground" />
                  <CardTitle>Execution Configuration</CardTitle>
                </div>
              </CardHeader>
              <CardContent>
                <ExecutionConfigEditor
                  initialValue={actionType?.execution ?? {}}
                  onSave={handleSaveExecution}
                  disabled={isNew}
                />
              </CardContent>
            </Card>
          </div>
        </TabsContent>
      </Tabs>

      <ConfirmDialog
        open={deleteOpen}
        onOpenChange={setDeleteOpen}
        title="Delete Action Type"
        description={
          deleteError
            ? `Error: ${deleteError}`
            : "Are you sure you want to delete this action type? This will acquire an edit lock and delete the entity. This action cannot be undone."
        }
        confirmLabel="Delete"
        variant="destructive"
        onConfirm={() => deleteMutation.mutate()}
        loading={deleteMutation.isPending}
      />
    </div>
  );
}
