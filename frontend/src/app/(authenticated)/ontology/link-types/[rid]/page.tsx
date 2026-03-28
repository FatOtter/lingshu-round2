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
import { Save, Trash2 } from "lucide-react";
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
    key: "version_status",
    label: "Status",
    render: (value) => {
      const status = value as string;
      const variant = status === "ACTIVE" ? "default" : status === "DRAFT" ? "secondary" : "outline";
      return <Badge variant={variant}>{status}</Badge>;
    },
  },
];

export default function LinkTypeEditorPage() {
  const params = useParams();
  const router = useRouter();
  const rid = params.rid as string;
  const queryClient = useQueryClient();

  const isNew = rid === "new";

  const { data, isLoading } = useQuery({
    queryKey: ["ontology", "link-type", rid],
    queryFn: () => ontologyApi.getLinkType(rid),
    enabled: !isNew,
  });

  const linkType = data?.data;

  const [apiName, setApiName] = useState("");
  const [displayName, setDisplayName] = useState("");
  const [description, setDescription] = useState("");
  const [sourceRid, setSourceRid] = useState("");
  const [targetRid, setTargetRid] = useState("");
  const [cardinality, setCardinality] = useState("MANY_TO_MANY");
  const [initialized, setInitialized] = useState(false);
  const [deleteOpen, setDeleteOpen] = useState(false);
  const [deleteError, setDeleteError] = useState<string | null>(null);

  if (!isNew && linkType && !initialized) {
    setApiName(linkType.api_name);
    setDisplayName(linkType.display_name);
    setDescription(linkType.description);
    setSourceRid(linkType.source_object_type_rid ?? "");
    setTargetRid(linkType.target_object_type_rid ?? "");
    setCardinality(linkType.cardinality);
    setInitialized(true);
  }

  const saveMutation = useMutation({
    mutationFn: () => {
      const payload = {
        api_name: apiName,
        display_name: displayName,
        description,
        source_object_type_rid: sourceRid,
        target_object_type_rid: targetRid,
        cardinality,
      };
      if (isNew) {
        return ontologyApi.createLinkType(payload);
      }
      return ontologyApi.updateLinkType(rid, payload);
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["ontology", "link-type", rid] });
      queryClient.invalidateQueries({ queryKey: ["ontology", "link-types"] });
    },
  });

  const deleteMutation = useMutation({
    mutationFn: async () => {
      await ontologyApi.acquireLock("link-types", rid);
      try {
        await ontologyApi.deleteLinkType(rid);
      } catch (err) {
        await ontologyApi.releaseLock("link-types", rid).catch(() => {});
        throw err;
      }
    },
    onSuccess: () => {
      setDeleteOpen(false);
      queryClient.invalidateQueries({ queryKey: ["ontology", "link-types"] });
      router.push("/ontology/link-types");
    },
    onError: (err) => {
      const message = err instanceof ApiClientError
        ? `${err.code}: ${err.message}`
        : "Failed to delete link type";
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
            {isNew ? "New Link Type" : linkType?.display_name ?? rid}
          </h1>
          {!isNew && linkType && (
            <p className="text-sm text-muted-foreground">{linkType.api_name}</p>
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

      <Tabs defaultValue="info">
        <TabsList>
          <TabsTrigger value="info">Info</TabsTrigger>
          <TabsTrigger value="properties">Properties</TabsTrigger>
        </TabsList>

        <TabsContent value="info">
          <div className="mt-4 grid max-w-xl gap-4">
            <div className="grid gap-1.5">
              <Label htmlFor="api_name">API Name</Label>
              <Input
                id="api_name"
                value={apiName}
                onChange={(e) => setApiName(e.target.value)}
                placeholder="e.g. my_link_type"
              />
            </div>
            <div className="grid gap-1.5">
              <Label htmlFor="display_name">Display Name</Label>
              <Input
                id="display_name"
                value={displayName}
                onChange={(e) => setDisplayName(e.target.value)}
                placeholder="e.g. My Link Type"
              />
            </div>
            <div className="grid gap-1.5">
              <Label htmlFor="description">Description</Label>
              <Textarea
                id="description"
                value={description}
                onChange={(e) => setDescription(e.target.value)}
                placeholder="Describe this link type..."
              />
            </div>
            <div className="grid gap-1.5">
              <Label htmlFor="source_rid">Source Object Type RID</Label>
              <Input
                id="source_rid"
                value={sourceRid}
                onChange={(e) => setSourceRid(e.target.value)}
                placeholder="e.g. ri.ontology.main.object-type.xxx"
              />
            </div>
            <div className="grid gap-1.5">
              <Label htmlFor="target_rid">Target Object Type RID</Label>
              <Input
                id="target_rid"
                value={targetRid}
                onChange={(e) => setTargetRid(e.target.value)}
                placeholder="e.g. ri.ontology.main.object-type.xxx"
              />
            </div>
            <div className="grid gap-1.5">
              <Label htmlFor="cardinality">Cardinality</Label>
              <Input
                id="cardinality"
                value={cardinality}
                onChange={(e) => setCardinality(e.target.value)}
                placeholder="ONE_TO_ONE | ONE_TO_MANY | MANY_TO_ONE | MANY_TO_MANY"
              />
            </div>
          </div>
        </TabsContent>

        <TabsContent value="properties">
          <div className="mt-4">
            <DataTable
              columns={propertyColumns}
              data={(linkType?.property_types ?? []) as unknown as Record<string, unknown>[]}
              total={linkType?.property_types?.length ?? 0}
              emptyMessage="No properties defined"
            />
          </div>
        </TabsContent>
      </Tabs>

      <ConfirmDialog
        open={deleteOpen}
        onOpenChange={setDeleteOpen}
        title="Delete Link Type"
        description={
          deleteError
            ? `Error: ${deleteError}`
            : "Are you sure you want to delete this link type? This will acquire an edit lock and delete the entity. This action cannot be undone."
        }
        confirmLabel="Delete"
        variant="destructive"
        onConfirm={() => deleteMutation.mutate()}
        loading={deleteMutation.isPending}
      />
    </div>
  );
}
