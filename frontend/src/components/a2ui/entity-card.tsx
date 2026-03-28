"use client";

import Link from "next/link";
import { Badge } from "@/components/ui/badge";
import type { A2UIEntityCard } from "@/types/a2ui";
import { ExternalLink } from "lucide-react";

interface A2UIEntityCardViewProps {
  data: A2UIEntityCard;
}

export function A2UIEntityCardView({ data }: A2UIEntityCardViewProps) {
  return (
    <div className="my-2 rounded-md border p-3">
      <div className="flex items-center gap-2">
        <Badge variant="outline" className="text-[10px]">
          {data.entity_type}
        </Badge>
        <span className="text-sm font-medium">{data.title}</span>
        {data.link && (
          <Link href={data.link} className="ml-auto text-muted-foreground hover:text-foreground">
            <ExternalLink className="size-3.5" />
          </Link>
        )}
      </div>

      {data.properties.length > 0 && (
        <div className="mt-2 grid grid-cols-2 gap-x-4 gap-y-1">
          {data.properties.map((prop, idx) => (
            <div key={idx} className="flex items-baseline justify-between gap-2 text-xs">
              <span className="text-muted-foreground">{prop.label}</span>
              <span className="font-medium">{prop.value}</span>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
