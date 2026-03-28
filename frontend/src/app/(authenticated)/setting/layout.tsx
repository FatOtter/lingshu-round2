"use client";

import { LayoutDashboard, Users, ScrollText, Building2 } from "lucide-react";
import { Sidebar, type SidebarItem } from "@/components/layout/sidebar";

const sidebarItems: SidebarItem[] = [
  {
    label: "Overview",
    href: "/setting/overview",
    icon: <LayoutDashboard className="size-4" />,
  },
  {
    label: "Users",
    href: "/setting/users",
    icon: <Users className="size-4" />,
  },
  {
    label: "Audit Logs",
    href: "/setting/audit",
    icon: <ScrollText className="size-4" />,
  },
  {
    label: "Tenants",
    href: "/setting/tenants",
    icon: <Building2 className="size-4" />,
  },
];

export default function SettingLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <div className="flex h-full w-full overflow-hidden">
      <Sidebar items={sidebarItems} title="Settings" />
      <div className="flex-1 overflow-auto p-6">{children}</div>
    </div>
  );
}
