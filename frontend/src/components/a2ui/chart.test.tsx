import { describe, it, expect, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import { A2UIChartView } from "./chart";
import type { A2UIChart } from "@/types/a2ui";

// recharts uses ResponsiveContainer which needs a real DOM size.
// Mock it to render children directly.
vi.mock("recharts", async () => {
  const actual = await vi.importActual<typeof import("recharts")>("recharts");
  return {
    ...actual,
    ResponsiveContainer: ({ children }: { children: React.ReactNode }) => (
      <div data-testid="responsive-container">{children}</div>
    ),
  };
});

function makeChart(overrides: Partial<A2UIChart> = {}): A2UIChart {
  return {
    type: "chart",
    chart_type: "bar",
    title: "Test Chart",
    x_axis: { label: "Month", values: ["Jan", "Feb", "Mar"] },
    y_axis: { label: "Revenue" },
    series: [{ name: "Sales", values: [10, 20, 30] }],
    ...overrides,
  };
}

describe("A2UIChartView", () => {
  it("renders chart title", () => {
    render(<A2UIChartView data={makeChart()} />);
    expect(screen.getByText("Test Chart")).toBeInTheDocument();
  });

  it("renders bar chart with responsive container", () => {
    render(<A2UIChartView data={makeChart({ chart_type: "bar" })} />);
    expect(screen.getByTestId("responsive-container")).toBeInTheDocument();
  });

  it("renders line chart", () => {
    render(<A2UIChartView data={makeChart({ chart_type: "line" })} />);
    expect(screen.getByTestId("responsive-container")).toBeInTheDocument();
    expect(screen.getByText("Test Chart")).toBeInTheDocument();
  });

  it("renders pie chart", () => {
    render(<A2UIChartView data={makeChart({ chart_type: "pie" })} />);
    expect(screen.getByTestId("responsive-container")).toBeInTheDocument();
  });

  it("renders area chart", () => {
    render(<A2UIChartView data={makeChart({ chart_type: "area" })} />);
    expect(screen.getByTestId("responsive-container")).toBeInTheDocument();
  });

  it("shows empty state when series is empty", () => {
    render(<A2UIChartView data={makeChart({ series: [] })} />);
    expect(screen.getByText("No data available")).toBeInTheDocument();
    expect(screen.getByText("Test Chart")).toBeInTheDocument();
    expect(screen.queryByTestId("responsive-container")).not.toBeInTheDocument();
  });

  it("renders multiple series", () => {
    const chart = makeChart({
      series: [
        { name: "Sales", values: [10, 20, 30] },
        { name: "Costs", values: [5, 10, 15] },
      ],
    });
    render(<A2UIChartView data={chart} />);
    expect(screen.getByTestId("responsive-container")).toBeInTheDocument();
  });
});
