"use client";

import { cn } from "@/lib/utils";
import type { A2UIMetricCard } from "@/types/a2ui";
import { TrendingUp, TrendingDown, Minus } from "lucide-react";

interface A2UIMetricCardViewProps {
  data: A2UIMetricCard;
}

const TREND_ICONS = {
  up: TrendingUp,
  down: TrendingDown,
  flat: Minus,
} as const;

export function A2UIMetricCardView({ data }: A2UIMetricCardViewProps) {
  return (
    <div className="my-2 grid grid-cols-2 gap-2 sm:grid-cols-3">
      {data.metrics.map((metric, idx) => {
        const TrendIcon = metric.trend ? TREND_ICONS[metric.trend] : null;
        return (
          <div
            key={idx}
            className="flex flex-col gap-0.5 rounded-md border p-2.5"
          >
            <span className="text-xs text-muted-foreground">{metric.label}</span>
            <div className="flex items-center gap-1.5">
              <span
                className={cn("text-lg font-semibold")}
                style={metric.color ? { color: metric.color } : undefined}
              >
                {metric.value}
              </span>
              {TrendIcon && (
                <TrendIcon
                  className={cn(
                    "size-3.5",
                    metric.trend === "up" && "text-green-500",
                    metric.trend === "down" && "text-red-500",
                    metric.trend === "flat" && "text-muted-foreground",
                  )}
                />
              )}
            </div>
          </div>
        );
      })}
    </div>
  );
}
