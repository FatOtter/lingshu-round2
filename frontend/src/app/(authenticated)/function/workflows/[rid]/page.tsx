"use client";

import { useEffect, useState } from "react";
import { useParams, useRouter } from "next/navigation";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { functionApi } from "@/lib/api/function";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { Badge } from "@/components/ui/badge";
import { Separator } from "@/components/ui/separator";
import { PageLoading } from "@/components/ui/loading";
import { DataTable, type ColumnDef } from "@/components/ui/data-table";
import { DagViewer } from "@/components/workflow/dag-viewer";
import { Save, Trash2, Play, Plus, X, Eye, List } from "lucide-react";
import { cn } from "@/lib/utils";
import type { Workflow, WorkflowNode, WorkflowEdge, WorkflowExecution } from "@/types/function";

const NODE_TYPES = ["action", "global_function", "condition", "wait"] as const;

const nodeColumns: ColumnDef<WorkflowNode>[] = [
  { key: "node_id", label: "Node ID" },
  {
    key: "type",
    label: "Type",
    render: (value) => <Badge variant="outline">{String(value)}</Badge>,
  },
  { key: "capability_rid", label: "Capability RID" },
  { key: "label", label: "Label" },
];

const edgeColumns: ColumnDef<WorkflowEdge>[] = [
  { key: "source_node_id", label: "Source" },
  { key: "target_node_id", label: "Target" },
  { key: "condition", label: "Condition" },
];

export default function WorkflowDetailPage() {
  const params = useParams<{ rid: string }>();
  const router = useRouter();
  const queryClient = useQueryClient();
  const rid = params.rid;
  const isNew = rid === "new";

  const [apiName, setApiName] = useState("");
  const [displayName, setDisplayName] = useState("");
  const [description, setDescription] = useState("");
  const [status, setStatus] = useState("draft");
  const [nodes, setNodes] = useState<WorkflowNode[]>([]);
  const [edges, setEdges] = useState<WorkflowEdge[]>([]);
  const [executionResult, setExecutionResult] = useState<WorkflowExecution | null>(null);
  const [activeTab, setActiveTab] = useState<"form" | "visual">("form");

  // New node form
  const [showNodeForm, setShowNodeForm] = useState(false);
  const [newNodeId, setNewNodeId] = useState("");
  const [newNodeType, setNewNodeType] = useState<string>("action");
  const [newNodeCapRid, setNewNodeCapRid] = useState("");
  const [newNodeLabel, setNewNodeLabel] = useState("");

  // New edge form
  const [showEdgeForm, setShowEdgeForm] = useState(false);
  const [newEdgeSrc, setNewEdgeSrc] = useState("");
  const [newEdgeTgt, setNewEdgeTgt] = useState("");
  const [newEdgeCondition, setNewEdgeCondition] = useState("");

  const { data: workflow, isLoading } = useQuery({
    queryKey: ["function", "workflow", rid],
    queryFn: () => functionApi.getWorkflow(rid),
    enabled: !isNew,
  });

  useEffect(() => {
    if (workflow?.data) {
      const wf = workflow.data;
      setApiName(wf.api_name);
      setDisplayName(wf.display_name);
      setDescription(wf.description ?? "");
      setStatus(wf.status);
      setNodes(wf.nodes ?? []);
      setEdges(wf.edges ?? []);
    }
  }, [workflow]);

  const saveMutation = useMutation({
    mutationFn: () => {
      const payload = {
        api_name: apiName,
        display_name: displayName,
        description: description || null,
        nodes,
        edges,
        status,
      };
      return isNew
        ? functionApi.createWorkflow(payload)
        : functionApi.updateWorkflow(rid, payload);
    },
    onSuccess: (res) => {
      queryClient.invalidateQueries({ queryKey: ["function", "workflows"] });
      if (isNew && res?.data?.rid) {
        router.replace(`/function/workflows/${res.data.rid}`);
      }
    },
  });

  const deleteMutation = useMutation({
    mutationFn: () => functionApi.deleteWorkflow(rid),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["function", "workflows"] });
      router.push("/function/workflows");
    },
  });

  const executeMutation = useMutation({
    mutationFn: () => functionApi.executeWorkflow(rid, {}),
    onSuccess: (res) => {
      if (res?.data) {
        setExecutionResult(res.data);
      }
    },
  });

  const addNode = () => {
    if (!newNodeId) return;
    const node: WorkflowNode = {
      node_id: newNodeId,
      type: newNodeType as WorkflowNode["type"],
      capability_rid: newNodeCapRid || null,
      input_mappings: {},
      position: { x: 0, y: nodes.length * 100 },
      label: newNodeLabel || null,
    };
    setNodes([...nodes, node]);
    setNewNodeId("");
    setNewNodeType("action");
    setNewNodeCapRid("");
    setNewNodeLabel("");
    setShowNodeForm(false);
  };

  const removeNode = (nodeId: string) => {
    setNodes(nodes.filter((n) => n.node_id !== nodeId));
    setEdges(edges.filter((e) => e.source_node_id !== nodeId && e.target_node_id !== nodeId));
  };

  const addEdge = () => {
    if (!newEdgeSrc || !newEdgeTgt) return;
    const edge: WorkflowEdge = {
      source_node_id: newEdgeSrc,
      target_node_id: newEdgeTgt,
      condition: newEdgeCondition || null,
    };
    setEdges([...edges, edge]);
    setNewEdgeSrc("");
    setNewEdgeTgt("");
    setNewEdgeCondition("");
    setShowEdgeForm(false);
  };

  const removeEdge = (idx: number) => {
    setEdges(edges.filter((_, i) => i !== idx));
  };

  if (isLoading && !isNew) {
    return <PageLoading />;
  }

  return (
    <div className="flex flex-col gap-6 p-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-xl font-semibold">
            {isNew ? "New Workflow" : displayName || apiName}
          </h1>
          {!isNew && (
            <Badge variant={status === "active" ? "default" : "secondary"} className="mt-1">
              {status}
            </Badge>
          )}
        </div>
        <div className="flex gap-2">
          {!isNew && (
            <>
              <Button
                variant="outline"
                onClick={() => executeMutation.mutate()}
                disabled={executeMutation.isPending}
              >
                <Play className="size-4" />
                Execute
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
          <Button onClick={() => saveMutation.mutate()} disabled={saveMutation.isPending}>
            <Save className="size-4" />
            {isNew ? "Create" : "Save"}
          </Button>
        </div>
      </div>

      <Separator />

      {/* Metadata */}
      <div className="grid max-w-xl gap-4">
        <div className="grid gap-1.5">
          <Label htmlFor="api_name">API Name</Label>
          <Input id="api_name" value={apiName} onChange={(e) => setApiName(e.target.value)} placeholder="e.g. data_pipeline" />
        </div>
        <div className="grid gap-1.5">
          <Label htmlFor="display_name">Display Name</Label>
          <Input id="display_name" value={displayName} onChange={(e) => setDisplayName(e.target.value)} placeholder="e.g. Data Pipeline" />
        </div>
        <div className="grid gap-1.5">
          <Label htmlFor="description">Description</Label>
          <Input id="description" value={description} onChange={(e) => setDescription(e.target.value)} placeholder="Optional description" />
        </div>
        <div className="grid gap-1.5">
          <Label htmlFor="status">Status</Label>
          <select
            id="status"
            value={status}
            onChange={(e) => setStatus(e.target.value)}
            className="flex h-9 w-full rounded-md border border-input bg-transparent px-3 py-1 text-sm shadow-sm"
          >
            <option value="draft">Draft</option>
            <option value="active">Active</option>
            <option value="archived">Archived</option>
          </select>
        </div>
      </div>

      <Separator />

      {/* Tab switcher */}
      <div className="flex gap-1 rounded-lg bg-muted p-1 w-fit">
        <button
          className={cn(
            "flex items-center gap-1.5 rounded-md px-3 py-1.5 text-sm font-medium transition-colors",
            activeTab === "form" ? "bg-background shadow-sm" : "text-muted-foreground hover:text-foreground",
          )}
          onClick={() => setActiveTab("form")}
        >
          <List className="size-3.5" />
          Source
        </button>
        <button
          className={cn(
            "flex items-center gap-1.5 rounded-md px-3 py-1.5 text-sm font-medium transition-colors",
            activeTab === "visual" ? "bg-background shadow-sm" : "text-muted-foreground hover:text-foreground",
          )}
          onClick={() => setActiveTab("visual")}
        >
          <Eye className="size-3.5" />
          Visual
        </button>
      </div>

      {/* Visual DAG tab */}
      {activeTab === "visual" && (
        <DagViewer nodes={nodes} edges={edges} />
      )}

      {/* Source (form) tab: Nodes */}
      {activeTab === "form" && (
      <>
      <div className="flex flex-col gap-3">
        <div className="flex items-center justify-between">
          <h2 className="text-lg font-medium">Nodes ({nodes.length})</h2>
          <Button variant="outline" size="sm" onClick={() => setShowNodeForm(!showNodeForm)}>
            {showNodeForm ? <X className="size-4" /> : <Plus className="size-4" />}
            {showNodeForm ? "Cancel" : "Add Node"}
          </Button>
        </div>

        {showNodeForm && (
          <div className="grid max-w-xl gap-3 rounded-md border p-4">
            <div className="grid gap-1.5">
              <Label>Node ID</Label>
              <Input value={newNodeId} onChange={(e) => setNewNodeId(e.target.value)} placeholder="e.g. step_1" />
            </div>
            <div className="grid gap-1.5">
              <Label>Type</Label>
              <select
                value={newNodeType}
                onChange={(e) => setNewNodeType(e.target.value)}
                className="flex h-9 w-full rounded-md border border-input bg-transparent px-3 py-1 text-sm shadow-sm"
              >
                {NODE_TYPES.map((t) => (
                  <option key={t} value={t}>{t}</option>
                ))}
              </select>
            </div>
            <div className="grid gap-1.5">
              <Label>Capability RID (optional)</Label>
              <Input value={newNodeCapRid} onChange={(e) => setNewNodeCapRid(e.target.value)} placeholder="ri.action.xxx" />
            </div>
            <div className="grid gap-1.5">
              <Label>Label (optional)</Label>
              <Input value={newNodeLabel} onChange={(e) => setNewNodeLabel(e.target.value)} placeholder="Step label" />
            </div>
            <Button size="sm" onClick={addNode}>Add</Button>
          </div>
        )}

        <DataTable
          columns={[
            ...nodeColumns,
            {
              key: "_actions",
              label: "",
              className: "w-[60px]",
              render: (_value, row) => {
                const n = row as unknown as WorkflowNode;
                return (
                  <Button variant="ghost" size="icon-sm" onClick={(e) => { e.stopPropagation(); removeNode(n.node_id); }}>
                    <Trash2 className="size-3.5" />
                  </Button>
                );
              },
            },
          ]}
          data={nodes as unknown as Record<string, unknown>[]}
          total={nodes.length}
          page={1}
          pageSize={100}
          onPageChange={() => {}}
          emptyMessage="No nodes"
        />
      </div>

      <Separator />

      {/* Edges */}
      <div className="flex flex-col gap-3">
        <div className="flex items-center justify-between">
          <h2 className="text-lg font-medium">Edges ({edges.length})</h2>
          <Button variant="outline" size="sm" onClick={() => setShowEdgeForm(!showEdgeForm)}>
            {showEdgeForm ? <X className="size-4" /> : <Plus className="size-4" />}
            {showEdgeForm ? "Cancel" : "Add Edge"}
          </Button>
        </div>

        {showEdgeForm && (
          <div className="grid max-w-xl gap-3 rounded-md border p-4">
            <div className="grid gap-1.5">
              <Label>Source Node ID</Label>
              <select
                value={newEdgeSrc}
                onChange={(e) => setNewEdgeSrc(e.target.value)}
                className="flex h-9 w-full rounded-md border border-input bg-transparent px-3 py-1 text-sm shadow-sm"
              >
                <option value="">Select source...</option>
                {nodes.map((n) => (
                  <option key={n.node_id} value={n.node_id}>{n.node_id}</option>
                ))}
              </select>
            </div>
            <div className="grid gap-1.5">
              <Label>Target Node ID</Label>
              <select
                value={newEdgeTgt}
                onChange={(e) => setNewEdgeTgt(e.target.value)}
                className="flex h-9 w-full rounded-md border border-input bg-transparent px-3 py-1 text-sm shadow-sm"
              >
                <option value="">Select target...</option>
                {nodes.map((n) => (
                  <option key={n.node_id} value={n.node_id}>{n.node_id}</option>
                ))}
              </select>
            </div>
            <div className="grid gap-1.5">
              <Label>Condition (optional)</Label>
              <Input value={newEdgeCondition} onChange={(e) => setNewEdgeCondition(e.target.value)} placeholder='e.g. step_1.status == ok' />
            </div>
            <Button size="sm" onClick={addEdge}>Add</Button>
          </div>
        )}

        <DataTable
          columns={[
            ...edgeColumns,
            {
              key: "_actions",
              label: "",
              className: "w-[60px]",
              render: (_value, row) => {
                const edge = row as unknown as WorkflowEdge;
                const idx = edges.findIndex(
                  (e) => e.source_node_id === edge.source_node_id && e.target_node_id === edge.target_node_id,
                );
                return (
                  <Button variant="ghost" size="icon-sm" onClick={(e) => { e.stopPropagation(); removeEdge(idx); }}>
                    <Trash2 className="size-3.5" />
                  </Button>
                );
              },
            },
          ]}
          data={edges as unknown as Record<string, unknown>[]}
          total={edges.length}
          page={1}
          pageSize={100}
          onPageChange={() => {}}
          emptyMessage="No edges"
        />
      </div>
      </>
      )}

      {/* Execution Result */}
      {executionResult && (
        <>
          <Separator />
          <div className="flex flex-col gap-3">
            <h2 className="text-lg font-medium">Execution Result</h2>
            <Badge variant={executionResult.status === "success" ? "default" : "secondary"}>
              {executionResult.status}
            </Badge>
            <Textarea
              readOnly
              value={JSON.stringify(executionResult, null, 2)}
              className="min-h-[200px] font-mono text-xs"
            />
          </div>
        </>
      )}
    </div>
  );
}
