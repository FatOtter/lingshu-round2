"use client";

import { useQuery } from "@tanstack/react-query";
import { ontologyApi } from "@/lib/api/ontology";
import { PageLoading } from "@/components/ui/loading";
import { Card, CardHeader, CardTitle, CardContent } from "@/components/ui/card";
import { TopologyGraph } from "@/components/ontology/topology-graph";
import { Box, Link2, Puzzle, Zap, Share2, Network } from "lucide-react";

export default function OntologyOverviewPage() {
  const { data: objectTypes, isLoading: loadingOT } = useQuery({
    queryKey: ["ontology", "object-types"],
    queryFn: () => ontologyApi.queryObjectTypes({ pagination: { page: 1, page_size: 1 } }),
  });

  const { data: linkTypes, isLoading: loadingLT } = useQuery({
    queryKey: ["ontology", "link-types"],
    queryFn: () => ontologyApi.queryLinkTypes({ pagination: { page: 1, page_size: 1 } }),
  });

  const { data: interfaceTypes, isLoading: loadingIT } = useQuery({
    queryKey: ["ontology", "interface-types"],
    queryFn: () => ontologyApi.queryInterfaceTypes({ pagination: { page: 1, page_size: 1 } }),
  });

  const { data: actionTypes, isLoading: loadingAT } = useQuery({
    queryKey: ["ontology", "action-types"],
    queryFn: () => ontologyApi.queryActionTypes({ pagination: { page: 1, page_size: 1 } }),
  });

  const { data: sharedPropertyTypes, isLoading: loadingSPT } = useQuery({
    queryKey: ["ontology", "shared-property-types"],
    queryFn: () => ontologyApi.querySharedPropertyTypes({ pagination: { page: 1, page_size: 1 } }),
  });

  const isLoading = loadingOT || loadingLT || loadingIT || loadingAT || loadingSPT;

  if (isLoading) {
    return <PageLoading />;
  }

  const stats = [
    { label: "Object Types", count: objectTypes?.pagination?.total ?? 0, icon: <Box className="size-5 text-blue-500" /> },
    { label: "Link Types", count: linkTypes?.pagination?.total ?? 0, icon: <Link2 className="size-5 text-green-500" /> },
    { label: "Interface Types", count: interfaceTypes?.pagination?.total ?? 0, icon: <Puzzle className="size-5 text-purple-500" /> },
    { label: "Action Types", count: actionTypes?.pagination?.total ?? 0, icon: <Zap className="size-5 text-orange-500" /> },
    { label: "Shared Property Types", count: sharedPropertyTypes?.pagination?.total ?? 0, icon: <Share2 className="size-5 text-teal-500" /> },
  ];

  return (
    <div className="flex flex-col gap-6">
      <div>
        <h1 className="text-xl font-semibold">Ontology Overview</h1>
        <p className="text-sm text-muted-foreground">Summary of all ontology entities</p>
      </div>

      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-5">
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
            <Network className="size-5 text-muted-foreground" />
            <CardTitle>Topology View</CardTitle>
          </div>
        </CardHeader>
        <CardContent>
          <TopologyGraph />
        </CardContent>
      </Card>
    </div>
  );
}
