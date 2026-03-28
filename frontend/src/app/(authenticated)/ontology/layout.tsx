"use client";

import { type ReactNode } from "react";
import { Sidebar, type SidebarItem } from "@/components/layout/sidebar";
import {
  LayoutDashboard,
  Box,
  Link2,
  Puzzle,
  Zap,
  Share2,
  List,
  Database,
  GitBranch,
} from "lucide-react";

const SIDEBAR_ITEMS: SidebarItem[] = [
  { label: "Overview", href: "/ontology/overview", icon: <LayoutDashboard className="size-4" /> },
  { label: "Object Types", href: "/ontology/object-types", icon: <Box className="size-4" /> },
  { label: "Link Types", href: "/ontology/link-types", icon: <Link2 className="size-4" /> },
  { label: "Interface Types", href: "/ontology/interface-types", icon: <Puzzle className="size-4" /> },
  { label: "Action Types", href: "/ontology/action-types", icon: <Zap className="size-4" /> },
  { label: "Shared Property Types", href: "/ontology/shared-property-types", icon: <Share2 className="size-4" /> },
  { label: "Properties", href: "/ontology/properties", icon: <List className="size-4" /> },
  { label: "Asset Mappings", href: "/ontology/asset-mappings", icon: <Database className="size-4" /> },
  { label: "Versions", href: "/ontology/versions", icon: <GitBranch className="size-4" /> },
];

export default function OntologyLayout({ children }: { children: ReactNode }) {
  return (
    <div className="flex flex-1 overflow-hidden">
      <Sidebar items={SIDEBAR_ITEMS} title="Ontology" />
      <div className="flex flex-1 flex-col overflow-auto p-6">{children}</div>
    </div>
  );
}
