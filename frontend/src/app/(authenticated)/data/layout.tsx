"use client";

import { type ReactNode } from "react";
import { Sidebar, type SidebarItem } from "@/components/layout/sidebar";
import {
  LayoutDashboard,
  Database,
  Search,
  GitBranch,
} from "lucide-react";

const SIDEBAR_ITEMS: SidebarItem[] = [
  { label: "Overview", href: "/data/overview", icon: <LayoutDashboard className="size-4" /> },
  { label: "Sources", href: "/data/sources", icon: <Database className="size-4" /> },
  { label: "Browse", href: "/data/browse", icon: <Search className="size-4" /> },
  { label: "Versions", href: "/data/versions", icon: <GitBranch className="size-4" /> },
];

export default function DataLayout({ children }: { children: ReactNode }) {
  return (
    <div className="flex flex-1 overflow-hidden">
      <Sidebar items={SIDEBAR_ITEMS} title="Data" />
      <div className="flex flex-1 flex-col overflow-auto p-6">{children}</div>
    </div>
  );
}
