"use client";

import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { ontologyApi } from "@/lib/api/ontology";
import { DataTable, type ColumnDef } from "@/components/ui/data-table";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { PageLoading } from "@/components/ui/loading";
import { Card, CardHeader, CardTitle, CardContent } from "@/components/ui/card";
import { ConfirmDialog } from "@/components/ui/confirm-dialog";
import { Upload, Trash2, History, RotateCcw } from "lucide-react";
import type { Snapshot, StagingSummary } from "@/types/ontology";
import { ApiClientError } from "@/lib/api/client";

export default function VersionsPage() {
  const queryClient = useQueryClient();
  const [page, setPage] = useState(1);
  const [publishOpen, setPublishOpen] = useState(false);
  const [discardOpen, setDiscardOpen] = useState(false);
  const [rollbackTarget, setRollbackTarget] = useState<Snapshot | null>(null);
  const [rollbackError, setRollbackError] = useState<string | null>(null);
  const pageSize = 20;

  const { data: stagingData, isLoading: loadingStaging, error: stagingError } = useQuery({
    queryKey: ["ontology", "staging-summary"],
    queryFn: () => ontologyApi.getStagingSummary(),
    retry: 1,
  });

  const { data: snapshotsData, isLoading: loadingSnapshots, error: snapshotsError } = useQuery({
    queryKey: ["ontology", "snapshots", page],
    queryFn: () => ontologyApi.querySnapshots({ offset: (page - 1) * pageSize, limit: pageSize }),
    retry: 1,
  });

  const staging: StagingSummary | undefined = stagingData?.data;
  const snapshots = snapshotsData?.data ?? [];
  const isLoading = loadingStaging || loadingSnapshots;

  const isCurrentSnapshot = (snapshot: Snapshot): boolean => {
    if (snapshots.length === 0) return false;
    return snapshot.snapshot_id === snapshots[0]?.snapshot_id && page === 1;
  };

  const commitMutation = useMutation({
    mutationFn: () => ontologyApi.commitStaging("Published from UI"),
    onSuccess: () => {
      setPublishOpen(false);
      queryClient.invalidateQueries({ queryKey: ["ontology", "staging-summary"] });
      queryClient.invalidateQueries({ queryKey: ["ontology", "snapshots"] });
    },
  });

  const discardMutation = useMutation({
    mutationFn: () => ontologyApi.discardStaging(),
    onSuccess: () => {
      setDiscardOpen(false);
      queryClient.invalidateQueries({ queryKey: ["ontology", "staging-summary"] });
    },
  });

  const rollbackMutation = useMutation({
    mutationFn: (snapshotId: string) => ontologyApi.rollbackSnapshot(snapshotId),
    onSuccess: () => {
      setRollbackTarget(null);
      setRollbackError(null);
      queryClient.invalidateQueries({ queryKey: ["ontology", "staging-summary"] });
      queryClient.invalidateQueries({ queryKey: ["ontology", "snapshots"] });
    },
    onError: (err) => {
      const message = err instanceof ApiClientError
        ? `${err.code}: ${err.message}`
        : "Failed to rollback snapshot. There may be uncommitted changes in staging.";
      setRollbackError(message);
    },
  });

  const snapshotColumns: ColumnDef<Snapshot>[] = [
    { key: "snapshot_id", label: "Snapshot ID", sortable: true },
    { key: "description", label: "Description" },
    { key: "created_by", label: "Created By" },
    {
      key: "created_at",
      label: "Created At",
      sortable: true,
      render: (value) => {
        const date = value as string;
        return date ? new Date(date).toLocaleString() : "-";
      },
    },
    { key: "entity_count", label: "Entities" },
    {
      key: "snapshot_id",
      label: "Actions",
      render: (_value, row) => {
        const snapshot = row as unknown as Snapshot;
        const isCurrent = isCurrentSnapshot(snapshot);
        return (
          <Button
            variant="outline"
            size="sm"
            disabled={isCurrent}
            onClick={(e) => {
              e.stopPropagation();
              setRollbackError(null);
              setRollbackTarget(snapshot);
            }}
          >
            <RotateCcw className="size-3.5" />
            {isCurrent ? "Current" : "Rollback"}
          </Button>
        );
      },
    },
  ];

  if (isLoading && !stagingData && !snapshotsData && !stagingError && !snapshotsError) {
    return <PageLoading />;
  }

  return (
    <div className="flex flex-col gap-6">
      <div>
        <h1 className="text-xl font-semibold">Version Management</h1>
        <p className="text-sm text-muted-foreground">Manage staging and publish ontology snapshots</p>
      </div>

      <Card>
        <CardHeader>
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2">
              <Upload className="size-5 text-muted-foreground" />
              <CardTitle>Staging Summary</CardTitle>
            </div>
            <div className="flex gap-2">
              <Button
                variant="destructive"
                size="sm"
                onClick={() => setDiscardOpen(true)}
                disabled={!staging?.total}
              >
                <Trash2 className="size-4" />
                Discard Staging
              </Button>
              <Button
                size="sm"
                onClick={() => setPublishOpen(true)}
                disabled={!staging?.total}
              >
                <Upload className="size-4" />
                Publish
              </Button>
            </div>
          </div>
        </CardHeader>
        <CardContent>
          {staging && staging.total > 0 ? (
            <div className="space-y-2">
              <p className="text-sm font-medium">{staging.total} change(s) in staging</p>
              {staging.changes && staging.changes.length > 0 ? (
                <div className="space-y-1">
                  {staging.changes.map((change) => (
                    <div
                      key={`${change.entity_type}-${change.rid}`}
                      className="flex items-center gap-2 text-sm"
                    >
                      <Badge
                        variant={
                          change.change_type === "created"
                            ? "default"
                            : change.change_type === "deleted"
                              ? "destructive"
                              : "secondary"
                        }
                      >
                        {change.change_type}
                      </Badge>
                      <span className="text-muted-foreground">{change.entity_type}</span>
                      <span>{change.api_name}</span>
                    </div>
                  ))}
                </div>
              ) : (
                <p className="text-sm text-muted-foreground">
                  {staging.total} pending entity changes
                </p>
              )}
            </div>
          ) : (
            <p className="text-sm text-muted-foreground">No changes in staging</p>
          )}
        </CardContent>
      </Card>

      <div>
        <div className="mb-4 flex items-center gap-2">
          <History className="size-5 text-muted-foreground" />
          <h2 className="text-lg font-semibold">Snapshot History</h2>
        </div>
        <DataTable
          columns={snapshotColumns}
          data={(snapshots) as unknown as Record<string, unknown>[]}
          total={snapshotsData?.pagination?.total ?? 0}
          page={page}
          pageSize={pageSize}
          onPageChange={setPage}
          loading={loadingSnapshots}
          emptyMessage="No snapshots yet"
        />
      </div>

      <ConfirmDialog
        open={publishOpen}
        onOpenChange={setPublishOpen}
        title="Publish Staging"
        description="This will commit all staged changes and create a new snapshot. This action cannot be undone."
        confirmLabel="Publish"
        onConfirm={() => commitMutation.mutate()}
        loading={commitMutation.isPending}
      />

      <ConfirmDialog
        open={discardOpen}
        onOpenChange={setDiscardOpen}
        title="Discard Staging"
        description="This will discard all staged changes. This action cannot be undone."
        confirmLabel="Discard"
        variant="destructive"
        onConfirm={() => discardMutation.mutate()}
        loading={discardMutation.isPending}
      />

      <ConfirmDialog
        open={!!rollbackTarget}
        onOpenChange={(open) => { if (!open) { setRollbackTarget(null); setRollbackError(null); } }}
        title="Rollback to Snapshot"
        description={
          rollbackError
            ? `Error: ${rollbackError}`
            : `Are you sure you want to rollback to snapshot "${rollbackTarget?.description ?? rollbackTarget?.snapshot_id}"? This will restore the ontology to the state of this snapshot. Any uncommitted staging changes must be discarded first.`
        }
        confirmLabel="Rollback"
        variant="destructive"
        onConfirm={() => {
          if (rollbackTarget) {
            rollbackMutation.mutate(rollbackTarget.snapshot_id);
          }
        }}
        loading={rollbackMutation.isPending}
      />
    </div>
  );
}
