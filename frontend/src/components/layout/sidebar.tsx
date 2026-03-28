"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { PanelLeftClose, PanelLeft } from "lucide-react";
import { useState, type ReactNode } from "react";
import { cn } from "@/lib/utils";
import { Button } from "@/components/ui/button";
import { ScrollArea } from "@/components/ui/scroll-area";

export interface SidebarItem {
  label: string;
  href: string;
  icon?: ReactNode;
}

interface SidebarProps {
  items: SidebarItem[];
  title?: string;
}

export function Sidebar({ items, title }: SidebarProps) {
  const pathname = usePathname();
  const [collapsed, setCollapsed] = useState(false);

  if (collapsed) {
    return (
      <div className="flex w-10 flex-col items-center border-r bg-card pt-2">
        <Button variant="ghost" size="icon-xs" onClick={() => setCollapsed(false)}>
          <PanelLeft className="size-4" />
        </Button>
      </div>
    );
  }

  return (
    <div className="flex w-[250px] flex-col border-r bg-card">
      <div className="flex items-center justify-between border-b px-3 py-2">
        {title && <span className="text-sm font-medium">{title}</span>}
        <Button variant="ghost" size="icon-xs" onClick={() => setCollapsed(true)} className="ml-auto">
          <PanelLeftClose className="size-4" />
        </Button>
      </div>
      <ScrollArea className="flex-1">
        <nav className="flex flex-col gap-0.5 p-2">
          {items.map((item) => {
            const isActive = pathname === item.href || pathname.startsWith(item.href + "/");
            return (
              <Link
                key={item.href}
                href={item.href}
                className={cn(
                  "flex items-center gap-2 rounded-md px-2.5 py-1.5 text-sm text-muted-foreground transition-colors hover:bg-accent hover:text-accent-foreground",
                  isActive && "bg-accent text-accent-foreground font-medium",
                )}
              >
                {item.icon}
                <span>{item.label}</span>
              </Link>
            );
          })}
        </nav>
      </ScrollArea>
    </div>
  );
}
