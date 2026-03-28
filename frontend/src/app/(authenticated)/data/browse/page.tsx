"use client";

import { useState, useMemo } from "react";
import { useQuery } from "@tanstack/react-query";
import { useRouter } from "next/navigation";
import { ontologyApi } from "@/lib/api/ontology";
import { useDebounce } from "@/hooks/use-debounce";
import { PageLoading } from "@/components/ui/loading";
import { Card, CardHeader, CardTitle, CardDescription, CardContent } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Input } from "@/components/ui/input";
import { Box, Link2, Search } from "lucide-react";
import type { ObjectType, LinkType } from "@/types/ontology";

export default function BrowseDataPage() {
  const router = useRouter();
  const [search, setSearch] = useState("");
  const debouncedSearch = useDebounce(search, 300);

  const { data: objectTypesData, isLoading: loadingOT } = useQuery({
    queryKey: ["ontology", "object-types", "browse"],
    queryFn: () => ontologyApi.queryObjectTypes({ limit: 200 }),
  });

  const { data: linkTypesData, isLoading: loadingLT } = useQuery({
    queryKey: ["ontology", "link-types", "browse"],
    queryFn: () => ontologyApi.queryLinkTypes({ limit: 200 }),
  });

  const isLoading = loadingOT || loadingLT;

  const allObjectTypes: ObjectType[] = objectTypesData?.data ?? [];
  const allLinkTypes: LinkType[] = linkTypesData?.data ?? [];

  // Client-side search filtering on type cards
  const objectTypes = useMemo(() => {
    if (!debouncedSearch) return allObjectTypes;
    const q = debouncedSearch.toLowerCase();
    return allObjectTypes.filter(
      (ot) =>
        ot.display_name.toLowerCase().includes(q) ||
        ot.api_name.toLowerCase().includes(q),
    );
  }, [allObjectTypes, debouncedSearch]);

  const linkTypes = useMemo(() => {
    if (!debouncedSearch) return allLinkTypes;
    const q = debouncedSearch.toLowerCase();
    return allLinkTypes.filter(
      (lt) =>
        lt.display_name.toLowerCase().includes(q) ||
        lt.api_name.toLowerCase().includes(q),
    );
  }, [allLinkTypes, debouncedSearch]);

  if (isLoading) {
    return <PageLoading />;
  }

  return (
    <div className="flex flex-col gap-6">
      <div>
        <h1 className="text-xl font-semibold">Browse Data</h1>
        <p className="text-sm text-muted-foreground">
          Select a type to browse its data instances
        </p>
      </div>

      {/* Search */}
      <div className="relative max-w-sm">
        <Search className="absolute left-2.5 top-1/2 size-4 -translate-y-1/2 text-muted-foreground" />
        <Input
          placeholder="Search types..."
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          className="pl-8"
        />
      </div>

      {objectTypes.length > 0 && (
        <section className="flex flex-col gap-3">
          <h2 className="text-base font-medium">Object Types</h2>
          <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4">
            {objectTypes.map((ot) => (
              <Card
                key={ot.rid}
                size="sm"
                className="cursor-pointer transition-shadow hover:shadow-md"
                onClick={() => router.push(`/data/browse/object-types/${ot.rid}`)}
              >
                <CardHeader>
                  <div className="flex items-center gap-2">
                    <Box className="size-4 text-blue-500" />
                    <CardTitle>{ot.display_name}</CardTitle>
                  </div>
                  <CardDescription>{ot.api_name}</CardDescription>
                </CardHeader>
                <CardContent>
                  <div className="flex items-center gap-2">
                    <Badge variant="secondary">{ot.property_types?.length ?? 0} properties</Badge>
                    <Badge variant="outline">{ot.version_status}</Badge>
                  </div>
                </CardContent>
              </Card>
            ))}
          </div>
        </section>
      )}

      {linkTypes.length > 0 && (
        <section className="flex flex-col gap-3">
          <h2 className="text-base font-medium">Link Types</h2>
          <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4">
            {linkTypes.map((lt) => (
              <Card
                key={lt.rid}
                size="sm"
                className="cursor-pointer transition-shadow hover:shadow-md"
                onClick={() => router.push(`/data/browse/link-types/${lt.rid}`)}
              >
                <CardHeader>
                  <div className="flex items-center gap-2">
                    <Link2 className="size-4 text-green-500" />
                    <CardTitle>{lt.display_name}</CardTitle>
                  </div>
                  <CardDescription>{lt.api_name}</CardDescription>
                </CardHeader>
                <CardContent>
                  <div className="flex items-center gap-2">
                    <Badge variant="secondary">{lt.cardinality}</Badge>
                    <Badge variant="outline">{lt.version_status}</Badge>
                  </div>
                </CardContent>
              </Card>
            ))}
          </div>
        </section>
      )}

      {objectTypes.length === 0 && linkTypes.length === 0 && (
        <div className="flex h-48 items-center justify-center rounded-lg border border-dashed text-muted-foreground">
          {debouncedSearch
            ? "No types match your search."
            : "No types with data found. Define types in the Ontology module first."}
        </div>
      )}
    </div>
  );
}
