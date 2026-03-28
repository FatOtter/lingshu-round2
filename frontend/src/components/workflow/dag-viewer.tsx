"use client";

import { useMemo } from "react";
import { cn } from "@/lib/utils";
import type { WorkflowNode, WorkflowEdge } from "@/types/function";

interface DagViewerProps {
  nodes: WorkflowNode[];
  edges: WorkflowEdge[];
}

// Layout constants
const NODE_W = 180;
const NODE_H = 60;
const DIAMOND_SIZE = 50;
const LAYER_GAP_Y = 120;
const NODE_GAP_X = 220;
const PADDING = 40;

interface LayoutNode {
  node: WorkflowNode;
  x: number;
  y: number;
  layer: number;
}

/**
 * Compute a simple layered layout using topological sort.
 */
function computeLayout(nodes: WorkflowNode[], edges: WorkflowEdge[]): LayoutNode[] {
  if (nodes.length === 0) return [];

  // Build adjacency and in-degree
  const adj = new Map<string, string[]>();
  const inDeg = new Map<string, number>();

  for (const n of nodes) {
    adj.set(n.node_id, []);
    inDeg.set(n.node_id, 0);
  }
  for (const e of edges) {
    adj.get(e.source_node_id)?.push(e.target_node_id);
    inDeg.set(e.target_node_id, (inDeg.get(e.target_node_id) ?? 0) + 1);
  }

  // Topological sort by layers (Kahn's algorithm)
  const layers: string[][] = [];
  let queue = nodes.filter((n) => (inDeg.get(n.node_id) ?? 0) === 0).map((n) => n.node_id);
  const visited = new Set<string>();

  while (queue.length > 0) {
    layers.push([...queue]);
    const next: string[] = [];
    for (const id of queue) {
      visited.add(id);
      for (const tgt of adj.get(id) ?? []) {
        const d = (inDeg.get(tgt) ?? 1) - 1;
        inDeg.set(tgt, d);
        if (d === 0 && !visited.has(tgt)) {
          next.push(tgt);
        }
      }
    }
    queue = next;
  }

  // Nodes not reached (cycles or disconnected) get placed in last layer
  const remaining = nodes.filter((n) => !visited.has(n.node_id)).map((n) => n.node_id);
  if (remaining.length > 0) {
    layers.push(remaining);
  }

  const nodeMap = new Map(nodes.map((n) => [n.node_id, n]));
  const result: LayoutNode[] = [];

  for (let layerIdx = 0; layerIdx < layers.length; layerIdx++) {
    const layer = layers[layerIdx];
    const layerWidth = layer.length * NODE_GAP_X;
    const startX = PADDING + (layerWidth > 0 ? 0 : 0);

    for (let i = 0; i < layer.length; i++) {
      const n = nodeMap.get(layer[i]);
      if (!n) continue;
      result.push({
        node: n,
        x: startX + i * NODE_GAP_X + (NODE_GAP_X - NODE_W) / 2,
        y: PADDING + layerIdx * LAYER_GAP_Y,
        layer: layerIdx,
      });
    }
  }

  return result;
}

function getNodeCenter(ln: LayoutNode): { cx: number; cy: number } {
  if (ln.node.type === "condition") {
    return { cx: ln.x + DIAMOND_SIZE, cy: ln.y + DIAMOND_SIZE };
  }
  return { cx: ln.x + NODE_W / 2, cy: ln.y + NODE_H / 2 };
}

function getNodeBottom(ln: LayoutNode): { x: number; y: number } {
  if (ln.node.type === "condition") {
    return { x: ln.x + DIAMOND_SIZE, y: ln.y + DIAMOND_SIZE * 2 };
  }
  return { x: ln.x + NODE_W / 2, y: ln.y + NODE_H };
}

function getNodeTop(ln: LayoutNode): { x: number; y: number } {
  if (ln.node.type === "condition") {
    return { x: ln.x + DIAMOND_SIZE, y: ln.y };
  }
  return { x: ln.x + NODE_W / 2, y: ln.y };
}

const TYPE_COLORS: Record<string, { fill: string; stroke: string; text: string }> = {
  action: { fill: "#eff6ff", stroke: "#3b82f6", text: "#1e40af" },
  global_function: { fill: "#f0fdf4", stroke: "#22c55e", text: "#166534" },
  condition: { fill: "#fefce8", stroke: "#eab308", text: "#854d0e" },
  wait: { fill: "#fdf4ff", stroke: "#a855f7", text: "#6b21a8" },
};

const TYPE_LABELS: Record<string, string> = {
  action: "Action",
  global_function: "Function",
  condition: "Condition",
  wait: "Wait",
};

export function DagViewer({ nodes, edges }: DagViewerProps) {
  const layout = useMemo(() => computeLayout(nodes, edges), [nodes, edges]);
  const layoutMap = useMemo(
    () => new Map(layout.map((ln) => [ln.node.node_id, ln])),
    [layout],
  );

  if (nodes.length === 0) {
    return (
      <div className="flex h-64 items-center justify-center rounded-md border border-dashed text-sm text-muted-foreground">
        Add nodes and edges to see the visual workflow.
      </div>
    );
  }

  // Calculate SVG dimensions
  const maxX = Math.max(...layout.map((ln) => ln.x + NODE_W)) + PADDING;
  const maxY = Math.max(...layout.map((ln) => ln.y + NODE_H)) + PADDING;
  const svgW = Math.max(maxX, 400);
  const svgH = Math.max(maxY, 200);

  return (
    <div className="overflow-auto rounded-md border bg-background">
      <svg width={svgW} height={svgH} className="min-w-full">
        <defs>
          <marker
            id="arrowhead"
            markerWidth="10"
            markerHeight="7"
            refX="9"
            refY="3.5"
            orient="auto"
          >
            <polygon points="0 0, 10 3.5, 0 7" fill="#94a3b8" />
          </marker>
        </defs>

        {/* Edges */}
        {edges.map((edge, i) => {
          const src = layoutMap.get(edge.source_node_id);
          const tgt = layoutMap.get(edge.target_node_id);
          if (!src || !tgt) return null;

          const from = getNodeBottom(src);
          const to = getNodeTop(tgt);

          // Simple path with a curve
          const midY = (from.y + to.y) / 2;
          const d = `M ${from.x} ${from.y} C ${from.x} ${midY}, ${to.x} ${midY}, ${to.x} ${to.y}`;

          return (
            <g key={`edge-${i}`}>
              <path
                d={d}
                fill="none"
                stroke="#94a3b8"
                strokeWidth={1.5}
                markerEnd="url(#arrowhead)"
              />
              {edge.condition && (
                <text
                  x={(from.x + to.x) / 2}
                  y={midY - 4}
                  textAnchor="middle"
                  className="fill-muted-foreground text-[10px]"
                >
                  {edge.condition}
                </text>
              )}
            </g>
          );
        })}

        {/* Nodes */}
        {layout.map((ln) => {
          const colors = TYPE_COLORS[ln.node.type] ?? TYPE_COLORS.action;
          const label = ln.node.label ?? ln.node.node_id;
          const typeLabel = TYPE_LABELS[ln.node.type] ?? ln.node.type;

          if (ln.node.type === "condition") {
            // Diamond shape
            const cx = ln.x + DIAMOND_SIZE;
            const cy = ln.y + DIAMOND_SIZE;
            const points = `${cx},${cy - DIAMOND_SIZE} ${cx + DIAMOND_SIZE},${cy} ${cx},${cy + DIAMOND_SIZE} ${cx - DIAMOND_SIZE},${cy}`;
            return (
              <g key={ln.node.node_id}>
                <polygon
                  points={points}
                  fill={colors.fill}
                  stroke={colors.stroke}
                  strokeWidth={1.5}
                />
                <text
                  x={cx}
                  y={cy - 4}
                  textAnchor="middle"
                  className="text-[11px] font-medium"
                  fill={colors.text}
                >
                  {label.length > 14 ? label.slice(0, 12) + "..." : label}
                </text>
                <text
                  x={cx}
                  y={cy + 12}
                  textAnchor="middle"
                  className="text-[9px]"
                  fill={colors.text}
                  opacity={0.7}
                >
                  {typeLabel}
                </text>
              </g>
            );
          }

          if (ln.node.type === "wait") {
            // Rounded rect with hourglass indicator
            return (
              <g key={ln.node.node_id}>
                <rect
                  x={ln.x}
                  y={ln.y}
                  width={NODE_W}
                  height={NODE_H}
                  rx={12}
                  ry={12}
                  fill={colors.fill}
                  stroke={colors.stroke}
                  strokeWidth={1.5}
                  strokeDasharray="6 3"
                />
                <text
                  x={ln.x + NODE_W / 2}
                  y={ln.y + NODE_H / 2 - 4}
                  textAnchor="middle"
                  className="text-[11px] font-medium"
                  fill={colors.text}
                >
                  {label.length > 18 ? label.slice(0, 16) + "..." : label}
                </text>
                <text
                  x={ln.x + NODE_W / 2}
                  y={ln.y + NODE_H / 2 + 12}
                  textAnchor="middle"
                  className="text-[9px]"
                  fill={colors.text}
                  opacity={0.7}
                >
                  {typeLabel}
                </text>
              </g>
            );
          }

          // Action or Function: rounded rect
          return (
            <g key={ln.node.node_id}>
              <rect
                x={ln.x}
                y={ln.y}
                width={NODE_W}
                height={NODE_H}
                rx={8}
                ry={8}
                fill={colors.fill}
                stroke={colors.stroke}
                strokeWidth={1.5}
              />
              <text
                x={ln.x + NODE_W / 2}
                y={ln.y + NODE_H / 2 - 4}
                textAnchor="middle"
                className="text-[11px] font-medium"
                fill={colors.text}
              >
                {label.length > 18 ? label.slice(0, 16) + "..." : label}
              </text>
              <text
                x={ln.x + NODE_W / 2}
                y={ln.y + NODE_H / 2 + 12}
                textAnchor="middle"
                className="text-[9px]"
                fill={colors.text}
                opacity={0.7}
              >
                {typeLabel}
              </text>
            </g>
          );
        })}
      </svg>
    </div>
  );
}
