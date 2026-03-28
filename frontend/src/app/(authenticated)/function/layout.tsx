"use client";

import { type ReactNode } from "react";
import { Sidebar, type SidebarItem } from "@/components/layout/sidebar";
import { LayoutDashboard, Blocks, GitBranch } from "lucide-react";

const SIDEBAR_ITEMS: SidebarItem[] = [
  { label: "Overview", href: "/function/overview", icon: <LayoutDashboard className="size-4" /> },
  { label: "Capabilities", href: "/function/capabilities", icon: <Blocks className="size-4" /> },
  { label: "Workflows", href: "/function/workflows", icon: <GitBranch className="size-4" /> },
];

export default function FunctionLayout({ children }: { children: ReactNode }) {
  return (
    <div className="flex flex-1 overflow-hidden">
      <Sidebar items={SIDEBAR_ITEMS} title="Function" />
      <div className="flex flex-1 flex-col overflow-auto p-6">{children}</div>
    </div>
  );
}
