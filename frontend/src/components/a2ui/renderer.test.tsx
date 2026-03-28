import { describe, it, expect, vi } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import { A2UIRenderer } from "./renderer";
import type { A2UIComponent } from "@/types/a2ui";

// Mock child components to avoid deep dependency chains
vi.mock("./table", () => ({
  A2UITableView: ({ data }: { data: { title: string; columns: { label: string }[]; rows: Record<string, unknown>[] } }) => (
    <div data-testid="table-view">
      <span>{data.title}</span>
      {data.columns.map((c) => (
        <span key={c.label}>{c.label}</span>
      ))}
      {data.rows.length === 0 ? (
        <span>No data</span>
      ) : (
        data.rows.map((row, i) => (
          <span key={i}>{Object.values(row).join(",")}</span>
        ))
      )}
    </div>
  ),
}));

vi.mock("./metric-card", () => ({
  A2UIMetricCardView: ({ data }: { data: { metrics: { label: string; value: string | number }[] } }) => (
    <div data-testid="metric-card-view">
      {data.metrics.map((m, i) => (
        <div key={i}>
          <span>{m.label}</span>
          <span>{m.value}</span>
        </div>
      ))}
    </div>
  ),
}));

vi.mock("./confirmation-card", () => ({
  A2UIConfirmationCardView: ({
    data,
    onApprove,
    onReject,
  }: {
    data: { title: string; description: string; affected_objects: { name: string }[]; side_effects: { category: string }[] };
    onApprove?: () => void;
    onReject?: () => void;
  }) => (
    <div data-testid="confirmation-card-view">
      <span>{data.title}</span>
      <span>{data.description}</span>
      {data.affected_objects.map((o, i) => (
        <span key={i}>{o.name}</span>
      ))}
      {data.side_effects.map((e, i) => (
        <span key={i}>{e.category}</span>
      ))}
      <button onClick={onApprove}>Approve</button>
      <button onClick={onReject}>Reject</button>
    </div>
  ),
}));

vi.mock("./entity-card", () => ({
  A2UIEntityCardView: ({
    data,
  }: {
    data: { entity_type: string; title: string; properties: { label: string; value: string | number }[] };
  }) => (
    <div data-testid="entity-card-view">
      <span>{data.entity_type}</span>
      <span>{data.title}</span>
      {data.properties.map((p, i) => (
        <div key={i}>
          <span>{p.label}</span>
          <span>{p.value}</span>
        </div>
      ))}
    </div>
  ),
}));

vi.mock("./chart", () => ({
  A2UIChartView: ({ data }: { data: { title: string } }) => (
    <div data-testid="chart-view">{data.title}</div>
  ),
}));

vi.mock("./form", () => ({
  A2UIFormView: ({ data, onSubmit }: { data: { title: string }; onSubmit?: (v: Record<string, unknown>) => void }) => (
    <div data-testid="form-view">{data.title}</div>
  ),
}));

describe("A2UIRenderer", () => {
  it("renders table component with title and data", () => {
    const table: A2UIComponent = {
      type: "table",
      title: "Employees",
      columns: [
        { key: "name", label: "Name" },
        { key: "role", label: "Role" },
      ],
      rows: [
        { name: "Alice", role: "Engineer" },
        { name: "Bob", role: "Manager" },
      ],
    };

    render(<A2UIRenderer component={table} />);

    expect(screen.getByTestId("table-view")).toBeInTheDocument();
    expect(screen.getByText("Employees")).toBeInTheDocument();
    expect(screen.getByText("Name")).toBeInTheDocument();
    expect(screen.getByText("Role")).toBeInTheDocument();
  });

  it("renders metric-card component with metrics", () => {
    const metricCard: A2UIComponent = {
      type: "metric_card",
      metrics: [
        { label: "Total Users", value: 42, trend: "up" },
        { label: "Revenue", value: "$1,000", trend: "down" },
      ],
    };

    render(<A2UIRenderer component={metricCard} />);

    expect(screen.getByTestId("metric-card-view")).toBeInTheDocument();
    expect(screen.getByText("Total Users")).toBeInTheDocument();
    expect(screen.getByText("42")).toBeInTheDocument();
    expect(screen.getByText("Revenue")).toBeInTheDocument();
    expect(screen.getByText("$1,000")).toBeInTheDocument();
  });

  it("renders confirmation-card with approve and reject buttons", () => {
    const onApprove = vi.fn();
    const onReject = vi.fn();

    const confirmation: A2UIComponent = {
      type: "confirmation_card",
      action_api_name: "delete-user",
      title: "Delete User",
      safety_level: "dangerous",
      description: "This will permanently delete the user.",
      affected_objects: [{ name: "User:Alice", operation: "delete" }],
      side_effects: [{ category: "data-loss" }],
    };

    render(
      <A2UIRenderer
        component={confirmation}
        onApprove={onApprove}
        onReject={onReject}
      />,
    );

    expect(screen.getByTestId("confirmation-card-view")).toBeInTheDocument();
    expect(screen.getByText("Delete User")).toBeInTheDocument();
    expect(screen.getByText("This will permanently delete the user.")).toBeInTheDocument();
    expect(screen.getByText("User:Alice")).toBeInTheDocument();
    expect(screen.getByText("data-loss")).toBeInTheDocument();

    fireEvent.click(screen.getByText("Approve"));
    expect(onApprove).toHaveBeenCalledTimes(1);

    fireEvent.click(screen.getByText("Reject"));
    expect(onReject).toHaveBeenCalledTimes(1);
  });

  it("renders entity-card with properties", () => {
    const entityCard: A2UIComponent = {
      type: "entity_card",
      entity_type: "ObjectType",
      entity_rid: "ri.obj.1",
      title: "Employee",
      properties: [
        { label: "Status", value: "Active" },
        { label: "Count", value: 150 },
      ],
    };

    render(<A2UIRenderer component={entityCard} />);

    expect(screen.getByTestId("entity-card-view")).toBeInTheDocument();
    expect(screen.getByText("ObjectType")).toBeInTheDocument();
    expect(screen.getByText("Employee")).toBeInTheDocument();
    expect(screen.getByText("Status")).toBeInTheDocument();
    expect(screen.getByText("Active")).toBeInTheDocument();
    expect(screen.getByText("150")).toBeInTheDocument();
  });

  it("renders unknown component type with fallback message", () => {
    const unknown = { type: "unknown_widget" } as unknown as A2UIComponent;

    render(<A2UIRenderer component={unknown} />);

    expect(screen.getByText(/Unknown component type: unknown_widget/)).toBeInTheDocument();
  });

  it("renders chart component", () => {
    const chart: A2UIComponent = {
      type: "chart",
      chart_type: "bar",
      title: "Sales Chart",
      x_axis: { label: "Month", values: ["Jan", "Feb"] },
      y_axis: { label: "Revenue" },
      series: [{ name: "2024", values: [100, 200] }],
    };

    render(<A2UIRenderer component={chart} />);

    expect(screen.getByTestId("chart-view")).toBeInTheDocument();
    expect(screen.getByText("Sales Chart")).toBeInTheDocument();
  });
});
