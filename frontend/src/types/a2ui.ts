export interface TableColumn {
  key: string;
  label: string;
  sortable?: boolean;
}

export interface TableAction {
  label: string;
  action_rid: string;
}

export interface A2UITable {
  type: "table";
  title: string;
  columns: TableColumn[];
  rows: Record<string, unknown>[];
  object_type_rid?: string;
  actions?: TableAction[];
}

export interface A2UIMetricCard {
  type: "metric_card";
  metrics: Array<{
    label: string;
    value: number | string;
    color?: string;
    trend?: "up" | "down" | "flat";
  }>;
}

export interface A2UIConfirmationCard {
  type: "confirmation_card";
  action_api_name: string;
  title: string;
  safety_level: string;
  description: string;
  affected_objects: Array<{ name: string; operation: string }>;
  side_effects: Array<{ category: string }>;
}

export interface A2UIEntityCard {
  type: "entity_card";
  entity_type: string;
  entity_rid: string;
  title: string;
  properties: Array<{ label: string; value: string | number }>;
  link?: string;
}

export interface A2UIChart {
  type: "chart";
  chart_type: "bar" | "line" | "pie" | "area";
  title: string;
  x_axis: { label: string; values: (string | number)[] };
  y_axis: { label: string };
  series: Array<{ name: string; values: number[] }>;
}

export interface A2UIFormField {
  key: string;
  label: string;
  type: "text" | "number" | "select" | "boolean" | "textarea";
  required?: boolean;
  default_value?: string | number | boolean;
  options?: Array<{ label: string; value: string }>;
  placeholder?: string;
}

export interface A2UIForm {
  type: "form";
  title: string;
  description?: string;
  fields: A2UIFormField[];
  submit_action_rid?: string;
  submit_label?: string;
}

export type A2UIComponent = A2UITable | A2UIMetricCard | A2UIConfirmationCard | A2UIEntityCard | A2UIChart | A2UIForm;
