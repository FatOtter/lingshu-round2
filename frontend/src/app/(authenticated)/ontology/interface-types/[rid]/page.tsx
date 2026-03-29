"use client";

import { useState } from "react";
import { useParams, useRouter } from "next/navigation";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { ontologyApi } from "@/lib/api/ontology";
import { PageLoading } from "@/components/ui/loading";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { Label } from "@/components/ui/label";
import { Tabs, TabsList, TabsTrigger, TabsContent } from "@/components/ui/tabs";
import { DataTable, type ColumnDef } from "@/components/ui/data-table";
import { ConfirmDialog } from "@/components/ui/confirm-dialog";
import { Save, Trash2, Upload } from "lucide-react";
import { ApiClientError } from "@/lib/api/client";

const ridColumns: ColumnDef<{ rid: string }>[] = [
  { key: "rid", label: "Shared Property Type RID" },
];

export default function InterfaceTypeEditorPage() {
  const params = useParams();
  const router = useRouter();
  const rid = params.rid as string;
  const queryClient = useQueryClient();

  const isNew = rid === "new";

  const { data, isLoading } = useQuery({
    queryKey: ["ontology", "interface-type", rid],
    queryFn: () => ontologyApi.getInterfaceType(rid),
    enabled: !isNew,
  });

  const interfaceType = data?.data;

  const [apiName, setApiName] = useState("");
  const [displayName, setDisplayName] = useState("");
  const [description, setDescription] = useState("");
  const [initialized, setInitialized] = useState(false);
  const [deleteOpen, setDeleteOpen] = useState(false);
  const [deleteError, setDeleteError] = useState<string | null>(null);

  if (!isNew && interfaceType && !initialized) {
    setApiName(interfaceType.api_name);
    setDisplayName(interfaceType.display_name);
    setDescription(interfaceType.description);
    setInitialized(true);
  }

  const [saveError, setSaveError] = useState<string | null>(null);

  const saveMutation = useMutation({
    mutationFn: () => {
      setSaveError(null);
      const payload = { api_name: apiName, display_name: displayName, description };
      if (isNew) {
        return ontologyApi.createInterfaceType(payload);
      }
      return ontologyApi.updateInterfaceType(rid, payload);
    },
    onSuccess: (result) => {
      queryClient.invalidateQueries({ queryKey: ["ontology", "interface-type", rid] });
      queryClient.invalidateQueries({ queryKey: ["ontology", "interface-types"] });
      if (isNew && result?.data?.rid) {
        router.push(`/ontology/interface-types/${result.data.rid}`);
      }
    },
    onError: (err) => {
      const message = err instanceof ApiClientError
        ? `${err.code}: ${err.message}`
        : "Failed to save interface type";
      setSaveError(message);
    },
  });

  const submitToStagingMutation = useMutation({
    mutationFn: () => ontologyApi.submitToStaging("interface-types", rid),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["ontology", "interface-type", rid] });
      queryClient.invalidateQueries({ queryKey: ["ontology", "interface-types"] });
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
      await ontologyApi.acquireLock("interface-types", rid);
      try {
        await ontologyApi.deleteInterfaceType(rid);
      } catch (err) {
        await ontologyApi.releaseLock("interface-types", rid).catch(() => {});
        throw err;
      }
    },
    onSuccess: () => {
      setDeleteOpen(false);
      queryClient.invalidateQueries({ queryKey: ["ontology", "interface-types"] });
      router.push("/ontology/interface-types");
    },
    onError: (err) => {
      const message = err instanceof ApiClientError
        ? `${err.code}: ${err.message}`
        : "Failed to delete interface type";
      setDeleteError(message);
    },
  });

  if (isLoading && !isNew) {
    return <PageLoading />;
  }

  return (
    <div className="flex flex-col gap-4">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-xl font-semibold">
            {isNew ? "New Interface Type" : interfaceType?.display_name ?? rid}
          </h1>
          {!isNew && interfaceType && (
            <p className="text-sm text-muted-foreground">{interfaceType.api_name}</p>
          )}
        </div>
        <div className="flex items-center gap-2">
          {!isNew && interfaceType?.version_status === "draft" && (
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
          <TabsTrigger value="properties">Required Properties</TabsTrigger>
          <TabsTrigger value="extends">Extends</TabsTrigger>
        </TabsList>

        <TabsContent value="info">
          <div className="mt-4 grid max-w-xl gap-4">
            <div className="grid gap-1.5">
              <Label htmlFor="api_name">API Name</Label>
              <Input
                id="api_name"
                value={apiName}
                onChange={(e) => setApiName(e.target.value)}
                placeholder="e.g. my_interface_type"
              />
            </div>
            <div className="grid gap-1.5">
              <Label htmlFor="display_name">Display Name</Label>
              <Input
                id="display_name"
                value={displayName}
                onChange={(e) => setDisplayName(e.target.value)}
                placeholder="e.g. My Interface Type"
              />
            </div>
            <div className="grid gap-1.5">
              <Label htmlFor="description">Description</Label>
              <Textarea
                id="description"
                value={description}
                onChange={(e) => setDescription(e.target.value)}
                placeholder="Describe this interface type..."
              />
            </div>
          </div>
        </TabsContent>

        <TabsContent value="properties">
          <div className="mt-4">
            <DataTable
              columns={ridColumns}
              data={(interfaceType?.required_shared_property_type_rids ?? []).map(r => ({ rid: r })) as unknown as Record<string, unknown>[]}
              total={interfaceType?.required_shared_property_type_rids?.length ?? 0}
              emptyMessage="No required properties defined"
            />
          </div>
        </TabsContent>

        <TabsContent value="extends">
          <div className="mt-4">
            {interfaceType?.extends_interface_type_rids && interfaceType.extends_interface_type_rids.length > 0 ? (
              <div className="flex flex-wrap gap-2">
                {interfaceType.extends_interface_type_rids.map((erid) => (
                  <Badge key={erid} variant="secondary">{erid}</Badge>
                ))}
              </div>
            ) : (
              <p className="text-sm text-muted-foreground">Does not extend any interfaces</p>
            )}
          </div>
        </TabsContent>
      </Tabs>

      <ConfirmDialog
        open={deleteOpen}
        onOpenChange={setDeleteOpen}
        title="Delete Interface Type"
        description={
          deleteError
            ? `Error: ${deleteError}`
            : "Are you sure you want to delete this interface type? This will acquire an edit lock and delete the entity. This action cannot be undone."
        }
        confirmLabel="Delete"
        variant="destructive"
        onConfirm={() => deleteMutation.mutate()}
        loading={deleteMutation.isPending}
      />
    </div>
  );
}
