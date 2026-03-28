"use client";

import Link from "next/link";
import { Diamond, LayoutGrid, Zap, Bot, Settings } from "lucide-react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";

const MODULES = [
  {
    icon: Diamond,
    title: "Ontology",
    description: "Manage type definitions, data mappings, and versions",
    href: "/ontology/overview",
  },
  {
    icon: LayoutGrid,
    title: "Data",
    description: "Connect data sources and browse instances",
    href: "/data/overview",
  },
  {
    icon: Zap,
    title: "Function",
    description: "Execute actions and manage capabilities",
    href: "/function/overview",
  },
  {
    icon: Bot,
    title: "Agent",
    description: "Chat with AI to accomplish tasks",
    href: "/agent/chat",
  },
  {
    icon: Settings,
    title: "Setting",
    description: "Users, tenants, audit logs",
    href: "/setting/overview",
  },
];

export default function HomePage() {
  return (
    <div className="flex-1 overflow-auto p-8">
      <div className="mx-auto max-w-4xl">
        <h1 className="mb-2 text-2xl font-bold">Welcome to LingShu</h1>
        <p className="mb-8 text-muted-foreground">
          Ontology-centric Data Operating System
        </p>

        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {MODULES.map(({ icon: Icon, title, description, href }) => (
            <Link key={href} href={href}>
              <Card className="transition-colors hover:bg-accent">
                <CardHeader className="pb-2">
                  <CardTitle className="flex items-center gap-2 text-base">
                    <Icon className="size-5" />
                    {title}
                  </CardTitle>
                </CardHeader>
                <CardContent>
                  <p className="text-sm text-muted-foreground">{description}</p>
                </CardContent>
              </Card>
            </Link>
          ))}
        </div>
      </div>
    </div>
  );
}
