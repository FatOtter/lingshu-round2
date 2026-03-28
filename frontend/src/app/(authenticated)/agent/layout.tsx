"use client";

import { type ReactNode } from "react";
import { Sidebar, type SidebarItem } from "@/components/layout/sidebar";
import {
  MessageSquare,
  History,
  Cpu,
  Wrench,
  Plug,
  Users,
  Activity,
} from "lucide-react";

const SIDEBAR_ITEMS: SidebarItem[] = [
  { label: "Chat", href: "/agent/chat", icon: <MessageSquare className="size-4" /> },
  { label: "Sessions", href: "/agent/sessions", icon: <History className="size-4" /> },
  { label: "Models", href: "/agent/models", icon: <Cpu className="size-4" /> },
  // P1 placeholders
  { label: "Skills", href: "/agent/skills", icon: <Wrench className="size-4" /> },
  { label: "MCP Servers", href: "/agent/mcp", icon: <Plug className="size-4" /> },
  { label: "Sub-Agents", href: "/agent/sub-agents", icon: <Users className="size-4" /> },
  { label: "Monitor", href: "/agent/monitor", icon: <Activity className="size-4" /> },
];

export default function AgentLayout({ children }: { children: ReactNode }) {
  return (
    <div className="flex flex-1 overflow-hidden">
      <Sidebar items={SIDEBAR_ITEMS} title="Agent" />
      <div className="flex flex-1 flex-col overflow-auto">{children}</div>
    </div>
  );
}
