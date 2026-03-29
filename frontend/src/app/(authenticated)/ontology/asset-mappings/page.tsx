"use client";

import { useQuery } from "@tanstack/react-query";
import { ontologyApi } from "@/lib/api/ontology";
import { PageLoading } from "@/components/ui/loading";
import { Card, CardHeader, CardTitle, CardContent } from "@/components/ui/card";
import { Database } from "lucide-react";
import type { ObjectType } from "@/types/ontology";

export default function AssetMappingsPage() {
  const { data, isLoading } = useQuery({
    queryKey: ["ontology", "object-types", "all-for-mappings"],
    queryFn: () => ontologyApi.queryObjectTypes({ pagination: { page: 1, page_size: 500 } }),
  });

  if (isLoading && !data) {
    return <PageLoading />;
  }

  const objectTypes: ObjectType[] = data?.data ?? [];

  return (
    <div className="flex flex-col gap-4">
      <div>
        <h1 className="text-xl font-semibold">Asset Mappings</h1>
        <p className="text-sm text-muted-foreground">
          Read-only overview of asset mappings across object types
        </p>
      </div>

      {objectTypes.length === 0 ? (
        <Card>
          <CardContent className="py-8">
            <p className="text-center text-sm text-muted-foreground">
              No object types with asset mappings found
            </p>
          </CardContent>
        </Card>
      ) : (
        <div className="grid grid-cols-1 gap-4 md:grid-cols-2 lg:grid-cols-3">
          {objectTypes.map((ot) => (
            <Card key={ot.rid} size="sm">
              <CardHeader>
                <div className="flex items-center gap-2">
                  <Database className="size-4 text-muted-foreground" />
                  <CardTitle>{ot.display_name}</CardTitle>
                </div>
              </CardHeader>
              <CardContent>
                <div className="space-y-1 text-sm">
                  <p className="text-muted-foreground">{ot.api_name}</p>
                  <p>{ot.property_types?.length ?? 0} properties</p>
                </div>
              </CardContent>
            </Card>
          ))}
        </div>
      )}
    </div>
  );
}
