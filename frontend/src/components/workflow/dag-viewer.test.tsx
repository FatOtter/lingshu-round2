import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import { DagViewer } from "./dag-viewer";
import type { WorkflowNode, WorkflowEdge } from "@/types/function";

vi.mock("@/lib/utils", () => ({
  cn: (...args: unknown[]) => args.filter(Boolean).join(" "),
}));

function makeNode(
  overrides: Partial<WorkflowNode> & { node_id: string; type: WorkflowNode["type"] },
): WorkflowNode {
  return {
    capability_rid: null,
    input_mappings: {},
    position: { x: 0, y: 0 },
    label: null,
    ...overrides,
  };
}

describe("DagViewer", () => {
  it("renders empty state with no nodes", () => {
    render(<DagViewer nodes={[]} edges={[]} />);

    expect(
      screen.getByText("Add nodes and edges to see the visual workflow."),
    ).toBeInTheDocument();
  });

  it("renders correct number of SVG node elements", () => {
    const nodes: WorkflowNode[] = [
      makeNode({ node_id: "n1", type: "action", label: "Step 1" }),
      makeNode({ node_id: "n2", type: "global_function", label: "Step 2" }),
      makeNode({ node_id: "n3", type: "wait", label: "Step 3" }),
    ];

    const { container } = render(<DagViewer nodes={nodes} edges={[]} />);

    // Each node renders a <g> containing a <rect> (action, function, wait all use rect)
    const rects = container.querySelectorAll("rect");
    expect(rects.length).toBe(3);

    expect(screen.getByText("Step 1")).toBeInTheDocument();
    expect(screen.getByText("Step 2")).toBeInTheDocument();
    expect(screen.getByText("Step 3")).toBeInTheDocument();
  });

  it("nodes colored by type (action=blue, function=green, condition=yellow, wait=purple)", () => {
    const nodes: WorkflowNode[] = [
      makeNode({ node_id: "n1", type: "action", label: "Action Node" }),
      makeNode({ node_id: "n2", type: "global_function", label: "Function Node" }),
      makeNode({ node_id: "n3", type: "condition", label: "Cond Node" }),
      makeNode({ node_id: "n4", type: "wait", label: "Wait Node" }),
    ];

    const { container } = render(<DagViewer nodes={nodes} edges={[]} />);

    // Action and function use rects, condition uses polygon
    const rects = container.querySelectorAll("rect");
    const polygons = container.querySelectorAll("polygon");

    // rects: action (#3b82f6), function (#22c55e), wait (#a855f7) = 3 rects
    const rectStrokes = Array.from(rects).map((r) => r.getAttribute("stroke"));
    expect(rectStrokes).toContain("#3b82f6"); // action blue
    expect(rectStrokes).toContain("#22c55e"); // function green
    expect(rectStrokes).toContain("#a855f7"); // wait purple

    // condition uses polygon with yellow stroke (#eab308)
    // Filter out the arrowhead polygon (which has fill="#94a3b8")
    const condPolygons = Array.from(polygons).filter(
      (p) => p.getAttribute("stroke") === "#eab308",
    );
    expect(condPolygons.length).toBe(1);
  });

  it("edges rendered as paths", () => {
    const nodes: WorkflowNode[] = [
      makeNode({ node_id: "n1", type: "action", label: "Start" }),
      makeNode({ node_id: "n2", type: "action", label: "End" }),
    ];
    const edges: WorkflowEdge[] = [
      { source_node_id: "n1", target_node_id: "n2", condition: null },
    ];

    const { container } = render(<DagViewer nodes={nodes} edges={edges} />);

    const paths = container.querySelectorAll("path");
    expect(paths.length).toBe(1);
  });

  it("condition edges show labels", () => {
    const nodes: WorkflowNode[] = [
      makeNode({ node_id: "n1", type: "condition", label: "Check" }),
      makeNode({ node_id: "n2", type: "action", label: "Yes Branch" }),
    ];
    const edges: WorkflowEdge[] = [
      { source_node_id: "n1", target_node_id: "n2", condition: "approved == true" },
    ];

    render(<DagViewer nodes={nodes} edges={edges} />);

    expect(screen.getByText("approved == true")).toBeInTheDocument();
  });
});
