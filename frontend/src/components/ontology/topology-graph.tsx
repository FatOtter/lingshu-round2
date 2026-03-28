"use client";

import { useCallback, useMemo } from "react";
import { useRouter } from "next/navigation";
import { useQuery } from "@tanstack/react-query";
import { Network } from "lucide-react";
import { ontologyApi } from "@/lib/api/ontology";
import type { TopologyNode, TopologyEdge } from "@/types/ontology";

const NODE_COLORS: Record<string, string> = {
  ObjectType: "#3b82f6",
  LinkType: "#22c55e",
  InterfaceType: "#a855f7",
  ActionType: "#f97316",
  SharedPropertyType: "#14b8a6",
};

const NODE_ROUTES: Record<string, string> = {
  ObjectType: "/ontology/object-types",
  LinkType: "/ontology/link-types",
  InterfaceType: "/ontology/interface-types",
  ActionType: "/ontology/action-types",
  SharedPropertyType: "/ontology/shared-property-types",
};

const NODE_WIDTH = 180;
const NODE_HEIGHT = 60;
const CANVAS_PADDING = 40;

interface LayoutNode {
  node: TopologyNode;
  x: number;
  y: number;
  color: string;
}

function layoutNodes(nodes: TopologyNode[]): LayoutNode[] {
  const grouped: Record<string, TopologyNode[]> = {};
  for (const node of nodes) {
    const type = node.type;
    if (!grouped[type]) {
      grouped[type] = [];
    }
    grouped[type].push(node);
  }

  const typeOrder = ["ObjectType", "LinkType", "InterfaceType", "ActionType", "SharedPropertyType"];
  const result: LayoutNode[] = [];
  let colIndex = 0;

  for (const type of typeOrder) {
    const group = grouped[type] ?? [];
    if (group.length === 0) continue;

    const color = NODE_COLORS[type] ?? "#6b7280";
    group.forEach((node, rowIndex) => {
      result.push({
        node,
        x: CANVAS_PADDING + colIndex * (NODE_WIDTH + 60),
        y: CANVAS_PADDING + rowIndex * (NODE_HEIGHT + 30),
        color,
      });
    });
    colIndex++;
  }

  return result;
}

function findNodePosition(layouts: LayoutNode[], rid: string): { x: number; y: number } | null {
  const layout = layouts.find((l) => l.node.rid === rid);
  if (!layout) return null;
  return { x: layout.x + NODE_WIDTH / 2, y: layout.y + NODE_HEIGHT / 2 };
}

export function TopologyGraph() {
  const router = useRouter();

  const { data, isLoading, error } = useQuery({
    queryKey: ["ontology", "topology"],
    queryFn: () => ontologyApi.getTopology(),
  });

  const topology = data?.data;
  const nodes = topology?.nodes ?? [];
  const edges = topology?.edges ?? [];

  const layouts = useMemo(() => layoutNodes(nodes), [nodes]);

  const maxX = useMemo(() => {
    if (layouts.length === 0) return 600;
    return Math.max(...layouts.map((l) => l.x + NODE_WIDTH)) + CANVAS_PADDING;
  }, [layouts]);

  const maxY = useMemo(() => {
    if (layouts.length === 0) return 400;
    return Math.max(...layouts.map((l) => l.y + NODE_HEIGHT)) + CANVAS_PADDING;
  }, [layouts]);

  const handleNodeClick = useCallback(
    (node: TopologyNode) => {
      const route = NODE_ROUTES[node.type];
      if (route) {
        router.push(`${route}/${node.rid}`);
      }
    },
    [router],
  );

  if (isLoading) {
    return (
      <div className="flex h-64 items-center justify-center text-muted-foreground">
        Loading topology...
      </div>
    );
  }

  if (error) {
    return (
      <div className="flex h-64 items-center justify-center text-muted-foreground">
        Failed to load topology data
      </div>
    );
  }

  if (nodes.length === 0) {
    return (
      <div className="flex h-64 flex-col items-center justify-center gap-3">
        <Network className="size-12 text-muted-foreground/50" />
        <p className="text-sm font-medium text-muted-foreground">Your ontology is empty</p>
        <p className="max-w-sm text-center text-xs text-muted-foreground/70">
          Start by creating an ObjectType to define your data model. Entity types and their
          relationships will appear here as an interactive topology graph.
        </p>
        <button
          type="button"
          className="mt-1 rounded-md bg-primary px-4 py-2 text-sm font-medium text-primary-foreground hover:bg-primary/90"
          onClick={() => router.push("/ontology/object-types/new")}
        >
          Create ObjectType
        </button>
      </div>
    );
  }

  return (
    <div className="flex flex-col gap-3">
      <div className="flex flex-wrap gap-3">
        {Object.entries(NODE_COLORS).map(([type, color]) => (
          <div key={type} className="flex items-center gap-1.5 text-xs text-muted-foreground">
            <div className="size-3 rounded" style={{ backgroundColor: color }} />
            {type}
          </div>
        ))}
      </div>

      <div className="overflow-auto rounded-lg border bg-muted/30">
        <svg width={maxX} height={maxY} className="min-h-[300px]">
          <defs>
            <marker
              id="arrowhead"
              markerWidth="10"
              markerHeight="7"
              refX="10"
              refY="3.5"
              orient="auto"
            >
              <polygon points="0 0, 10 3.5, 0 7" fill="#9ca3af" />
            </marker>
          </defs>

          {edges.map((edge: TopologyEdge, idx: number) => {
            const from = findNodePosition(layouts, edge.source);
            const to = findNodePosition(layouts, edge.target);
            if (!from || !to) return null;
            return (
              <g key={idx}>
                <line
                  x1={from.x}
                  y1={from.y}
                  x2={to.x}
                  y2={to.y}
                  stroke="#9ca3af"
                  strokeWidth={1.5}
                  markerEnd="url(#arrowhead)"
                />
                {edge.label && (
                  <text
                    x={(from.x + to.x) / 2}
                    y={(from.y + to.y) / 2 - 6}
                    textAnchor="middle"
                    className="fill-muted-foreground text-[10px]"
                  >
                    {edge.label}
                  </text>
                )}
              </g>
            );
          })}

          {layouts.map((layout) => (
            <g
              key={layout.node.rid}
              className="cursor-pointer"
              onClick={() => handleNodeClick(layout.node)}
            >
              <rect
                x={layout.x}
                y={layout.y}
                width={NODE_WIDTH}
                height={NODE_HEIGHT}
                rx={8}
                fill={layout.color}
                fillOpacity={0.15}
                stroke={layout.color}
                strokeWidth={2}
              />
              <text
                x={layout.x + NODE_WIDTH / 2}
                y={layout.y + 24}
                textAnchor="middle"
                className="fill-foreground text-xs font-medium"
              >
                {layout.node.display_name.length > 20
                  ? layout.node.display_name.slice(0, 18) + "..."
                  : layout.node.display_name}
              </text>
              <text
                x={layout.x + NODE_WIDTH / 2}
                y={layout.y + 42}
                textAnchor="middle"
                className="fill-muted-foreground text-[10px]"
              >
                {layout.node.type}
              </text>
            </g>
          ))}
        </svg>
      </div>
    </div>
  );
}
