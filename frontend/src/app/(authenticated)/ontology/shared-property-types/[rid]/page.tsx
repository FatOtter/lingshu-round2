"use client";

import { useState } from "react";
import { useParams, useRouter } from "next/navigation";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { ontologyApi } from "@/lib/api/ontology";
import { PageLoading } from "@/components/ui/loading";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { Label } from "@/components/ui/label";
import { ConfirmDialog } from "@/components/ui/confirm-dialog";
import { Save, Trash2 } from "lucide-react";
import { ApiClientError } from "@/lib/api/client";

export default function SharedPropertyTypeEditorPage() {
  const params = useParams();
  const router = useRouter();
  const rid = params.rid as string;
  const queryClient = useQueryClient();

  const isNew = rid === "new";

  const { data, isLoading } = useQuery({
    queryKey: ["ontology", "shared-property-type", rid],
    queryFn: () => ontologyApi.getSharedPropertyType(rid),
    enabled: !isNew,
  });

  const sharedPropertyType = data?.data;

  const [apiName, setApiName] = useState("");
  const [displayName, setDisplayName] = useState("");
  const [description, setDescription] = useState("");
  const [dataType, setDataType] = useState("STRING");
  const [initialized, setInitialized] = useState(false);
  const [deleteOpen, setDeleteOpen] = useState(false);
  const [deleteError, setDeleteError] = useState<string | null>(null);

  if (!isNew && sharedPropertyType && !initialized) {
    setApiName(sharedPropertyType.api_name);
    setDisplayName(sharedPropertyType.display_name);
    setDescription(sharedPropertyType.description);
    setDataType(sharedPropertyType.data_type);
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
        data_type: dataType,
      };
      if (isNew) {
        return ontologyApi.createSharedPropertyType(payload);
      }
      return ontologyApi.updateSharedPropertyType(rid, payload);
    },
    onSuccess: (result) => {
      queryClient.invalidateQueries({ queryKey: ["ontology", "shared-property-type", rid] });
      queryClient.invalidateQueries({ queryKey: ["ontology", "shared-property-types"] });
      if (isNew && result?.data?.rid) {
        router.push(`/ontology/shared-property-types/${result.data.rid}`);
      }
    },
    onError: (err) => {
      const message = err instanceof ApiClientError
        ? `${err.code}: ${err.message}`
        : "Failed to save shared property type";
      setSaveError(message);
    },
  });

  const deleteMutation = useMutation({
    mutationFn: async () => {
      await ontologyApi.acquireLock("shared-property-types", rid);
      try {
        await ontologyApi.deleteSharedPropertyType(rid);
      } catch (err) {
        await ontologyApi.releaseLock("shared-property-types", rid).catch(() => {});
        throw err;
      }
    },
    onSuccess: () => {
      setDeleteOpen(false);
      queryClient.invalidateQueries({ queryKey: ["ontology", "shared-property-types"] });
      router.push("/ontology/shared-property-types");
    },
    onError: (err) => {
      const message = err instanceof ApiClientError
        ? `${err.code}: ${err.message}`
        : "Failed to delete shared property type";
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
            {isNew ? "New Shared Property Type" : sharedPropertyType?.display_name ?? rid}
          </h1>
          {!isNew && sharedPropertyType && (
            <p className="text-sm text-muted-foreground">{sharedPropertyType.api_name}</p>
          )}
        </div>
        <div className="flex items-center gap-2">
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

      <div className="grid max-w-xl gap-4">
        <div className="grid gap-1.5">
          <Label htmlFor="api_name">API Name</Label>
          <Input
            id="api_name"
            value={apiName}
            onChange={(e) => setApiName(e.target.value)}
            placeholder="e.g. my_shared_property"
          />
        </div>
        <div className="grid gap-1.5">
          <Label htmlFor="display_name">Display Name</Label>
          <Input
            id="display_name"
            value={displayName}
            onChange={(e) => setDisplayName(e.target.value)}
            placeholder="e.g. My Shared Property"
          />
        </div>
        <div className="grid gap-1.5">
          <Label htmlFor="description">Description</Label>
          <Textarea
            id="description"
            value={description}
            onChange={(e) => setDescription(e.target.value)}
            placeholder="Describe this shared property type..."
          />
        </div>
        <div className="grid gap-1.5">
          <Label htmlFor="data_type">Data Type</Label>
          <Input
            id="data_type"
            value={dataType}
            onChange={(e) => setDataType(e.target.value)}
            placeholder="STRING | INTEGER | FLOAT | BOOLEAN | DATE | ..."
          />
        </div>
      </div>

      <ConfirmDialog
        open={deleteOpen}
        onOpenChange={setDeleteOpen}
        title="Delete Shared Property Type"
        description={
          deleteError
            ? `Error: ${deleteError}`
            : "Are you sure you want to delete this shared property type? This will acquire an edit lock and delete the entity. This action cannot be undone."
        }
        confirmLabel="Delete"
        variant="destructive"
        onConfirm={() => deleteMutation.mutate()}
        loading={deleteMutation.isPending}
      />
    </div>
  );
}
