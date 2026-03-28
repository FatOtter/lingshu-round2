"use client";

import { useQuery } from "@tanstack/react-query";
import { copilotApi } from "@/lib/api/copilot";
import { PageLoading } from "@/components/ui/loading";
import { Card, CardHeader, CardTitle, CardContent } from "@/components/ui/card";
import { MessageSquare, Cpu, Wrench, Plug, Users, Activity } from "lucide-react";

export default function AgentOverviewPage() {
  const { data: sessions, isLoading: loadingSessions } = useQuery({
    queryKey: ["copilot", "sessions", "count"],
    queryFn: () => copilotApi.querySessions({ pagination: { page: 1, page_size: 1 } }),
  });

  const { data: models, isLoading: loadingModels } = useQuery({
    queryKey: ["copilot", "models", "count"],
    queryFn: () => copilotApi.queryModels({ pagination: { page: 1, page_size: 1 } }),
  });

  const { data: skills, isLoading: loadingSkills } = useQuery({
    queryKey: ["copilot", "skills", "count"],
    queryFn: () => copilotApi.querySkills({ pagination: { page: 1, page_size: 1 } }),
  });

  const { data: mcps, isLoading: loadingMcps } = useQuery({
    queryKey: ["copilot", "mcp", "count"],
    queryFn: () => copilotApi.queryMcp({ pagination: { page: 1, page_size: 1 } }),
  });

  const { data: subAgents, isLoading: loadingSubAgents } = useQuery({
    queryKey: ["copilot", "sub-agents", "count"],
    queryFn: () => copilotApi.querySubAgents({ pagination: { page: 1, page_size: 1 } }),
  });

  if (loadingSessions && loadingModels && loadingSkills && loadingMcps && loadingSubAgents) {
    return <PageLoading />;
  }

  const stats = [
    { label: "Sessions", count: sessions?.pagination?.total ?? 0, icon: <MessageSquare className="size-5 text-blue-500" /> },
    { label: "Models", count: models?.pagination?.total ?? 0, icon: <Cpu className="size-5 text-purple-500" /> },
    { label: "Skills", count: skills?.pagination?.total ?? 0, icon: <Wrench className="size-5 text-green-500" /> },
    { label: "MCP Servers", count: mcps?.pagination?.total ?? 0, icon: <Plug className="size-5 text-orange-500" /> },
    { label: "Sub-Agents", count: subAgents?.pagination?.total ?? 0, icon: <Users className="size-5 text-cyan-500" /> },
  ];

  return (
    <div className="flex flex-col gap-6">
      <div>
        <h1 className="text-xl font-semibold">Agent Overview</h1>
        <p className="text-sm text-muted-foreground">Copilot resources and configuration summary</p>
      </div>

      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
        {stats.map((stat) => (
          <Card key={stat.label} size="sm">
            <CardHeader>
              <div className="flex items-center gap-2">
                {stat.icon}
                <CardTitle>{stat.label}</CardTitle>
              </div>
            </CardHeader>
            <CardContent>
              <p className="text-2xl font-bold">{stat.count}</p>
            </CardContent>
          </Card>
        ))}
      </div>

      <Card>
        <CardHeader>
          <div className="flex items-center gap-2">
            <Activity className="size-5 text-muted-foreground" />
            <CardTitle>Quick Start</CardTitle>
          </div>
        </CardHeader>
        <CardContent>
          <p className="text-sm text-muted-foreground">
            Use the sidebar to navigate to Chat, configure Models, manage Skills, or monitor agent activity.
          </p>
        </CardContent>
      </Card>
    </div>
  );
}
