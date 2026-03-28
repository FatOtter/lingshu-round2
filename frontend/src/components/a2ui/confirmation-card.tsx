"use client";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Separator } from "@/components/ui/separator";
import type { A2UIConfirmationCard } from "@/types/a2ui";
import { ShieldAlert, ShieldCheck, Shield } from "lucide-react";

interface A2UIConfirmationCardViewProps {
  data: A2UIConfirmationCard;
  onApprove?: () => void;
  onReject?: () => void;
}

const SAFETY_CONFIG: Record<string, { icon: typeof Shield; variant: "default" | "secondary" | "destructive" | "outline" }> = {
  safe: { icon: ShieldCheck, variant: "secondary" },
  moderate: { icon: Shield, variant: "default" },
  dangerous: { icon: ShieldAlert, variant: "destructive" },
};

export function A2UIConfirmationCardView({
  data,
  onApprove,
  onReject,
}: A2UIConfirmationCardViewProps) {
  const safety = SAFETY_CONFIG[data.safety_level] ?? SAFETY_CONFIG.moderate;
  const SafetyIcon = safety.icon;

  return (
    <div className="my-2 rounded-md border p-3">
      <div className="flex items-center gap-2">
        <SafetyIcon className="size-4" />
        <span className="text-sm font-medium">{data.title}</span>
        <Badge variant={safety.variant} className="ml-auto text-xs">
          {data.safety_level}
        </Badge>
      </div>

      <p className="mt-1.5 text-xs text-muted-foreground">{data.description}</p>

      {data.affected_objects.length > 0 && (
        <>
          <Separator className="my-2" />
          <div className="flex flex-col gap-1">
            <span className="text-xs font-medium">Affected Objects</span>
            {data.affected_objects.map((obj, idx) => (
              <div key={idx} className="flex items-center gap-2 text-xs text-muted-foreground">
                <span>{obj.name}</span>
                <Badge variant="outline" className="text-[10px]">
                  {obj.operation}
                </Badge>
              </div>
            ))}
          </div>
        </>
      )}

      {data.side_effects.length > 0 && (
        <>
          <Separator className="my-2" />
          <div className="flex flex-col gap-1">
            <span className="text-xs font-medium">Side Effects</span>
            {data.side_effects.map((effect, idx) => (
              <span key={idx} className="text-xs text-muted-foreground">
                {effect.category}
              </span>
            ))}
          </div>
        </>
      )}

      <div className="mt-3 flex gap-2">
        <Button size="sm" variant="default" onClick={onApprove}>
          Approve
        </Button>
        <Button size="sm" variant="outline" onClick={onReject}>
          Reject
        </Button>
      </div>
    </div>
  );
}
