"use client";

import type { A2UIChart } from "@/types/a2ui";
import {
  ResponsiveContainer,
  BarChart,
  Bar,
  LineChart,
  Line,
  PieChart,
  Pie,
  AreaChart,
  Area,
  XAxis,
  YAxis,
  Tooltip,
  CartesianGrid,
  Cell,
  Legend,
} from "recharts";

interface A2UIChartViewProps {
  data: A2UIChart;
}

const DEFAULT_COLORS = ["#3b82f6", "#22c55e", "#a855f7", "#f97316", "#14b8a6"];

function getColor(index: number): string {
  return DEFAULT_COLORS[index % DEFAULT_COLORS.length];
}

function buildChartData(chart: A2UIChart): Record<string, unknown>[] {
  const { x_axis, series } = chart;
  return x_axis.values.map((label, i) => {
    const point: Record<string, unknown> = { label: String(label) };
    for (const s of series) {
      point[s.name] = s.values[i] ?? 0;
    }
    return point;
  });
}

function buildPieData(chart: A2UIChart): Array<{ name: string; value: number }> {
  const { x_axis, series } = chart;
  const firstSeries = series[0];
  if (!firstSeries) return [];
  return x_axis.values.map((label, i) => ({
    name: String(label),
    value: firstSeries.values[i] ?? 0,
  }));
}

function renderBarChart(chart: A2UIChart) {
  const chartData = buildChartData(chart);
  return (
    <ResponsiveContainer width="100%" height={300}>
      <BarChart data={chartData}>
        <CartesianGrid strokeDasharray="3 3" />
        <XAxis dataKey="label" label={chart.x_axis.label ? { value: chart.x_axis.label, position: "insideBottom", offset: -5 } : undefined} />
        <YAxis label={chart.y_axis.label ? { value: chart.y_axis.label, angle: -90, position: "insideLeft" } : undefined} />
        <Tooltip />
        <Legend />
        {chart.series.map((s, i) => (
          <Bar key={s.name} dataKey={s.name} fill={getColor(i)} />
        ))}
      </BarChart>
    </ResponsiveContainer>
  );
}

function renderLineChart(chart: A2UIChart) {
  const chartData = buildChartData(chart);
  return (
    <ResponsiveContainer width="100%" height={300}>
      <LineChart data={chartData}>
        <CartesianGrid strokeDasharray="3 3" />
        <XAxis dataKey="label" label={chart.x_axis.label ? { value: chart.x_axis.label, position: "insideBottom", offset: -5 } : undefined} />
        <YAxis label={chart.y_axis.label ? { value: chart.y_axis.label, angle: -90, position: "insideLeft" } : undefined} />
        <Tooltip />
        <Legend />
        {chart.series.map((s, i) => (
          <Line key={s.name} type="monotone" dataKey={s.name} stroke={getColor(i)} />
        ))}
      </LineChart>
    </ResponsiveContainer>
  );
}

function renderPieChart(chart: A2UIChart) {
  const pieData = buildPieData(chart);
  return (
    <ResponsiveContainer width="100%" height={300}>
      <PieChart>
        <Tooltip />
        <Legend />
        <Pie data={pieData} dataKey="value" nameKey="name" cx="50%" cy="50%" outerRadius={100} label>
          {pieData.map((_, i) => (
            <Cell key={i} fill={getColor(i)} />
          ))}
        </Pie>
      </PieChart>
    </ResponsiveContainer>
  );
}

function renderAreaChart(chart: A2UIChart) {
  const chartData = buildChartData(chart);
  return (
    <ResponsiveContainer width="100%" height={300}>
      <AreaChart data={chartData}>
        <CartesianGrid strokeDasharray="3 3" />
        <XAxis dataKey="label" label={chart.x_axis.label ? { value: chart.x_axis.label, position: "insideBottom", offset: -5 } : undefined} />
        <YAxis label={chart.y_axis.label ? { value: chart.y_axis.label, angle: -90, position: "insideLeft" } : undefined} />
        <Tooltip />
        <Legend />
        {chart.series.map((s, i) => (
          <Area key={s.name} type="monotone" dataKey={s.name} fill={getColor(i)} stroke={getColor(i)} fillOpacity={0.3} />
        ))}
      </AreaChart>
    </ResponsiveContainer>
  );
}

const CHART_RENDERERS: Record<A2UIChart["chart_type"], (chart: A2UIChart) => React.ReactNode> = {
  bar: renderBarChart,
  line: renderLineChart,
  pie: renderPieChart,
  area: renderAreaChart,
};

export function A2UIChartView({ data }: A2UIChartViewProps) {
  const renderer = CHART_RENDERERS[data.chart_type] ?? renderBarChart;

  if (data.series.length === 0) {
    return (
      <div className="my-2 flex flex-col items-center gap-2 rounded-md border p-6">
        <span className="text-sm font-medium">{data.title}</span>
        <span className="text-xs text-muted-foreground">No data available</span>
      </div>
    );
  }

  return (
    <div className="my-2 flex flex-col gap-2 rounded-md border p-4">
      <span className="text-sm font-medium">{data.title}</span>
      {renderer(data)}
    </div>
  );
}
