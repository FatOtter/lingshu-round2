"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { cn } from "@/lib/utils";
import {
  Diamond,
  LayoutGrid,
  Zap,
  Bot,
  Settings,
} from "lucide-react";
import { Tooltip, TooltipContent, TooltipTrigger } from "@/components/ui/tooltip";

const NAV_ITEMS = [
  { icon: Diamond, label: "Ontology", href: "/ontology", module: "ontology" },
  { icon: LayoutGrid, label: "Data", href: "/data", module: "data" },
  { icon: Zap, label: "Function", href: "/function", module: "function" },
  { icon: Bot, label: "Agent", href: "/agent", module: "agent" },
  { icon: Settings, label: "Setting", href: "/setting", module: "setting" },
] as const;

export function Dock() {
  const pathname = usePathname();

  return (
    <nav className="flex h-full w-16 flex-col items-center border-r bg-card py-4">
      <div className="flex flex-1 flex-col items-center gap-1">
        {NAV_ITEMS.map(({ icon: Icon, label, href, module }) => {
          const isActive = pathname.startsWith(href);
          return (
            <Tooltip key={module}>
              <TooltipTrigger
                render={
                  <Link
                    href={`${href}/overview`}
                    className={cn(
                      "flex h-12 w-12 flex-col items-center justify-center rounded-lg text-muted-foreground transition-colors hover:bg-accent hover:text-accent-foreground",
                      isActive && "bg-accent text-accent-foreground",
                    )}
                  />
                }
              >
                <Icon className="size-5" />
                <span className="mt-0.5 text-[10px] leading-none">{label}</span>
              </TooltipTrigger>
              <TooltipContent side="right" sideOffset={4}>
                {label}
              </TooltipContent>
            </Tooltip>
          );
        })}
      </div>
    </nav>
  );
}
