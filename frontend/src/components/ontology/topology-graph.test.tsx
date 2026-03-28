import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import { TopologyGraph } from "./topology-graph";
import type { TopologyNode, TopologyEdge } from "@/types/ontology";

const mockPush = vi.fn();

vi.mock("next/navigation", () => ({
  useRouter: () => ({ push: mockPush }),
}));

let mockQueryReturn: {
  data: { data: { nodes: TopologyNode[]; edges: TopologyEdge[] } | null } | undefined;
  isLoading: boolean;
  error: Error | null;
};

vi.mock("@tanstack/react-query", () => ({
  useQuery: () => mockQueryReturn,
}));

vi.mock("@/lib/api/ontology", () => ({
  ontologyApi: {
    getTopology: vi.fn(),
  },
}));

beforeEach(() => {
  vi.clearAllMocks();
  mockQueryReturn = {
    data: { data: { nodes: [], edges: [] } },
    isLoading: false,
    error: null,
  };
});

describe("TopologyGraph", () => {
  it("renders empty state when no topology data", () => {
    mockQueryReturn = {
      data: { data: { nodes: [], edges: [] } },
      isLoading: false,
      error: null,
    };

    render(<TopologyGraph />);

    expect(screen.getByText("Your ontology is empty")).toBeInTheDocument();
    expect(screen.getByText("Create ObjectType")).toBeInTheDocument();
  });

  it("renders SVG nodes for each entity type", () => {
    const nodes: TopologyNode[] = [
      { rid: "ri.obj.1", type: "ObjectType", api_name: "employee", display_name: "Employee" },
      { rid: "ri.link.1", type: "LinkType", api_name: "works_at", display_name: "Works At" },
      { rid: "ri.iface.1", type: "InterfaceType", api_name: "auditable", display_name: "Auditable" },
    ];

    mockQueryReturn = {
      data: { data: { nodes, edges: [] } },
      isLoading: false,
      error: null,
    };

    const { container } = render(<TopologyGraph />);

    expect(screen.getByText("Employee")).toBeInTheDocument();
    expect(screen.getByText("Works At")).toBeInTheDocument();
    expect(screen.getByText("Auditable")).toBeInTheDocument();

    const rects = container.querySelectorAll("rect");
    expect(rects.length).toBe(3);
  });

  it("nodes have correct colors by type (blue for ObjectType, green for LinkType, etc.)", () => {
    const nodes: TopologyNode[] = [
      { rid: "ri.obj.1", type: "ObjectType", api_name: "employee", display_name: "Employee" },
      { rid: "ri.link.1", type: "LinkType", api_name: "works_at", display_name: "Works At" },
      { rid: "ri.iface.1", type: "InterfaceType", api_name: "auditable", display_name: "Auditable" },
      { rid: "ri.action.1", type: "ActionType", api_name: "delete", display_name: "Delete" },
      { rid: "ri.shprop.1", type: "SharedPropertyType", api_name: "name", display_name: "Name" },
    ];

    mockQueryReturn = {
      data: { data: { nodes, edges: [] } },
      isLoading: false,
      error: null,
    };

    const { container } = render(<TopologyGraph />);

    const rects = container.querySelectorAll("rect");
    const colors = Array.from(rects).map((r) => r.getAttribute("stroke"));

    expect(colors).toContain("#3b82f6"); // ObjectType blue
    expect(colors).toContain("#22c55e"); // LinkType green
    expect(colors).toContain("#a855f7"); // InterfaceType purple
    expect(colors).toContain("#f97316"); // ActionType orange
    expect(colors).toContain("#14b8a6"); // SharedPropertyType teal
  });

  it("renders edges between connected nodes", () => {
    const nodes: TopologyNode[] = [
      { rid: "ri.obj.1", type: "ObjectType", api_name: "employee", display_name: "Employee" },
      { rid: "ri.obj.2", type: "ObjectType", api_name: "department", display_name: "Department" },
    ];
    const edges: TopologyEdge[] = [
      { source: "ri.obj.1", target: "ri.obj.2", label: "belongs_to" },
    ];

    mockQueryReturn = {
      data: { data: { nodes, edges } },
      isLoading: false,
      error: null,
    };

    const { container } = render(<TopologyGraph />);

    const lines = container.querySelectorAll("line");
    expect(lines.length).toBe(1);

    expect(screen.getByText("belongs_to")).toBeInTheDocument();
  });

  it("clicking a node calls router.push with correct path", () => {
    const nodes: TopologyNode[] = [
      { rid: "ri.obj.1", type: "ObjectType", api_name: "employee", display_name: "Employee" },
    ];

    mockQueryReturn = {
      data: { data: { nodes, edges: [] } },
      isLoading: false,
      error: null,
    };

    const { container } = render(<TopologyGraph />);

    const nodeGroup = container.querySelector("g.cursor-pointer");
    expect(nodeGroup).not.toBeNull();
    fireEvent.click(nodeGroup!);

    expect(mockPush).toHaveBeenCalledWith("/ontology/object-types/ri.obj.1");
  });
});
