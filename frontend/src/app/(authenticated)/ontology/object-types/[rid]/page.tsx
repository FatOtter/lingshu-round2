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
import { Card, CardHeader, CardTitle, CardContent } from "@/components/ui/card";
import { ConfirmDialog } from "@/components/ui/confirm-dialog";
import { AssetMappingEditor } from "@/components/ontology/asset-mapping-editor";
import { Save, Database, Trash2, Upload } from "lucide-react";
import type { PropertyType } from "@/types/ontology";
import { ApiClientError } from "@/lib/api/client";

const propertyColumns: ColumnDef<PropertyType>[] = [
  { key: "api_name", label: "API Name", sortable: true },
  { key: "display_name", label: "Display Name" },
  { key: "data_type", label: "Data Type" },
  {
    key: "is_required",
    label: "Required",
    render: (value) => (value ? "Yes" : "No"),
  },
  {
    key: "is_array",
    label: "Array",
    render: (value) => (value ? "Yes" : "No"),
  },
  {
    key: "version_status",
    label: "Status",
    render: (value) => {
      const status = value as string;
      const variant = status === "ACTIVE" ? "default" : status === "DRAFT" ? "secondary" : "outline";
      return <Badge variant={variant}>{status}</Badge>;
    },
  },
];

export default function ObjectTypeEditorPage() {
  const params = useParams();
  const router = useRouter();
  const rid = params.rid as string;
  const queryClient = useQueryClient();

  const isNew = rid === "new";

  const { data, isLoading } = useQuery({
    queryKey: ["ontology", "object-type", rid],
    queryFn: () => ontologyApi.getObjectTypeDraft(rid),
    enabled: !isNew,
  });

  const objectType = data?.data;

  const [apiName, setApiName] = useState("");
  const [displayName, setDisplayName] = useState("");
  const [description, setDescription] = useState("");
  const [initialized, setInitialized] = useState(false);
  const [deleteOpen, setDeleteOpen] = useState(false);
  const [deleteError, setDeleteError] = useState<string | null>(null);

  if (!isNew && objectType && !initialized) {
    setApiName(objectType.api_name);
    setDisplayName(objectType.display_name);
    setDescription(objectType.description);
    setInitialized(true);
  }

  const [saveError, setSaveError] = useState<string | null>(null);

  const saveMutation = useMutation({
    mutationFn: () => {
      setSaveError(null);
      const payload = { api_name: apiName, display_name: displayName, description };
      if (isNew) {
        return ontologyApi.createObjectType(payload);
      }
      return ontologyApi.updateObjectType(rid, payload);
    },
    onSuccess: (result) => {
      queryClient.invalidateQueries({ queryKey: ["ontology", "object-type", rid] });
      queryClient.invalidateQueries({ queryKey: ["ontology", "object-types"] });
      if (isNew && result?.data?.rid) {
        router.push(`/ontology/object-types/${result.data.rid}`);
      }
    },
    onError: (err) => {
      const message = err instanceof ApiClientError
        ? `${err.code}: ${err.message}`
        : "Failed to save object type";
      setSaveError(message);
    },
  });

  const submitToStagingMutation = useMutation({
    mutationFn: () => ontologyApi.submitToStaging("object-types", rid),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["ontology", "object-type", rid] });
      queryClient.invalidateQueries({ queryKey: ["ontology", "object-types"] });
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
      await ontologyApi.acquireLock("object-types", rid);
      try {
        await ontologyApi.deleteObjectType(rid);
      } catch (err) {
        await ontologyApi.releaseLock("object-types", rid).catch(() => {});
        throw err;
      }
    },
    onSuccess: () => {
      setDeleteOpen(false);
      queryClient.invalidateQueries({ queryKey: ["ontology", "object-types"] });
      router.push("/ontology/object-types");
    },
    onError: (err) => {
      const message = err instanceof ApiClientError
        ? `${err.code}: ${err.message}`
        : "Failed to delete object type";
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
            {isNew ? "New Object Type" : objectType?.display_name ?? rid}
          </h1>
          {!isNew && objectType && (
            <p className="text-sm text-muted-foreground">{objectType.api_name}</p>
          )}
        </div>
        <div className="flex items-center gap-2">
          {!isNew && objectType?.version_status === "draft" && (
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
          <TabsTrigger value="properties">Properties</TabsTrigger>
          <TabsTrigger value="interfaces">Interfaces</TabsTrigger>
          <TabsTrigger value="data-mapping">Data Mapping</TabsTrigger>
        </TabsList>

        <TabsContent value="info">
          <div className="mt-4 grid max-w-xl gap-4">
            <div className="grid gap-1.5">
              <Label htmlFor="api_name">API Name</Label>
              <Input
                id="api_name"
                value={apiName}
                onChange={(e) => setApiName(e.target.value)}
                placeholder="e.g. my_object_type"
              />
            </div>
            <div className="grid gap-1.5">
              <Label htmlFor="display_name">Display Name</Label>
              <Input
                id="display_name"
                value={displayName}
                onChange={(e) => setDisplayName(e.target.value)}
                placeholder="e.g. My Object Type"
              />
            </div>
            <div className="grid gap-1.5">
              <Label htmlFor="description">Description</Label>
              <Textarea
                id="description"
                value={description}
                onChange={(e) => setDescription(e.target.value)}
                placeholder="Describe this object type..."
              />
            </div>
          </div>
        </TabsContent>

        <TabsContent value="properties">
          <div className="mt-4">
            <DataTable
              columns={propertyColumns}
              data={(objectType?.property_types ?? []) as unknown as Record<string, unknown>[]}
              total={objectType?.property_types?.length ?? 0}
              emptyMessage="No properties defined"
            />
          </div>
        </TabsContent>

        <TabsContent value="interfaces">
          <div className="mt-4">
            {objectType?.implements_interface_type_rids && objectType.implements_interface_type_rids.length > 0 ? (
              <div className="flex flex-wrap gap-2">
                {objectType.implements_interface_type_rids.map((irid) => (
                  <Badge key={irid} variant="secondary">{irid}</Badge>
                ))}
              </div>
            ) : (
              <p className="text-sm text-muted-foreground">No interfaces implemented</p>
            )}
          </div>
        </TabsContent>

        <TabsContent value="data-mapping">
          <div className="mt-4">
            <Card>
              <CardHeader>
                <div className="flex items-center gap-2">
                  <Database className="size-5 text-muted-foreground" />
                  <CardTitle>Configure AssetMapping</CardTitle>
                </div>
              </CardHeader>
              <CardContent>
                <AssetMappingEditor
                  rid={rid}
                  assetMapping={objectType?.asset_mapping ?? null}
                  properties={objectType?.property_types ?? []}
                  onSave={(mapping) => ontologyApi.updateObjectType(rid, { asset_mapping: mapping }).then(() => {
                    queryClient.invalidateQueries({ queryKey: ["ontology", "object-type", rid] });
                  })}
                />
              </CardContent>
            </Card>
          </div>
        </TabsContent>
      </Tabs>

      <ConfirmDialog
        open={deleteOpen}
        onOpenChange={setDeleteOpen}
        title="Delete Object Type"
        description={
          deleteError
            ? `Error: ${deleteError}`
            : "Are you sure you want to delete this object type? This will acquire an edit lock and delete the entity. This action cannot be undone."
        }
        confirmLabel="Delete"
        variant="destructive"
        onConfirm={() => deleteMutation.mutate()}
        loading={deleteMutation.isPending}
      />
    </div>
  );
}
