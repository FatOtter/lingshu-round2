"use client";

import type { A2UIComponent } from "@/types/a2ui";
import { A2UITableView } from "./table";
import { A2UIMetricCardView } from "./metric-card";
import { A2UIConfirmationCardView } from "./confirmation-card";
import { A2UIEntityCardView } from "./entity-card";
import { A2UIChartView } from "./chart";
import { A2UIFormView } from "./form";

interface A2UIRendererProps {
  component: A2UIComponent;
  onApprove?: () => void;
  onReject?: () => void;
  onSubmit?: (values: Record<string, unknown>) => void;
}

export function A2UIRenderer({ component, onApprove, onReject, onSubmit }: A2UIRendererProps) {
  switch (component.type) {
    case "table":
      return <A2UITableView data={component} />;
    case "metric_card":
      return <A2UIMetricCardView data={component} />;
    case "confirmation_card":
      return (
        <A2UIConfirmationCardView
          data={component}
          onApprove={onApprove}
          onReject={onReject}
        />
      );
    case "entity_card":
      return <A2UIEntityCardView data={component} />;
    case "chart":
      return <A2UIChartView data={component} />;
    case "form":
      return <A2UIFormView data={component} onSubmit={onSubmit} />;
    default:
      return (
        <div className="my-2 rounded-md border p-2 text-xs text-muted-foreground">
          Unknown component type: {(component as Record<string, unknown>).type as string}
        </div>
      );
  }
}
