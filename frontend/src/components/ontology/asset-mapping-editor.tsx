"use client";

import { useState, useCallback } from "react";
import { useQuery } from "@tanstack/react-query";
import { dataApi } from "@/lib/api/data";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Save, Plus, X } from "lucide-react";
import type { PropertyType } from "@/types/ontology";

interface ColumnMapping {
  property_api_name: string;
  column_name: string;
}

interface AssetMapping {
  connection_rid: string;
  schema_name: string;
  table_name: string;
  column_mappings: ColumnMapping[];
}

interface AssetMappingEditorProps {
  rid: string;
  assetMapping: Record<string, unknown> | null;
  properties: PropertyType[];
  onSave: (mapping: AssetMapping) => Promise<void>;
}

function parseMapping(raw: Record<string, unknown> | null): AssetMapping {
  if (!raw) {
    return { connection_rid: "", schema_name: "", table_name: "", column_mappings: [] };
  }
  return {
    connection_rid: (raw.connection_rid as string) ?? "",
    schema_name: (raw.schema_name as string) ?? "",
    table_name: (raw.table_name as string) ?? "",
    column_mappings: Array.isArray(raw.column_mappings)
      ? (raw.column_mappings as ColumnMapping[])
      : [],
  };
}

export function AssetMappingEditor({ assetMapping, properties, onSave }: AssetMappingEditorProps) {
  const initial = parseMapping(assetMapping);
  const [connectionRid, setConnectionRid] = useState(initial.connection_rid);
  const [schemaName, setSchemaName] = useState(initial.schema_name);
  const [tableName, setTableName] = useState(initial.table_name);
  const [columnMappings, setColumnMappings] = useState<ColumnMapping[]>(initial.column_mappings);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const { data: connectionsData } = useQuery({
    queryKey: ["data", "connections"],
    queryFn: () => dataApi.queryConnections({ pagination: { page: 1, page_size: 100 } }),
  });

  const connections = connectionsData?.data ?? [];

  const handleAddMapping = useCallback(() => {
    setColumnMappings((prev) => [...prev, { property_api_name: "", column_name: "" }]);
  }, []);

  const handleRemoveMapping = useCallback((index: number) => {
    setColumnMappings((prev) => prev.filter((_, i) => i !== index));
  }, []);

  const handleUpdateMapping = useCallback((index: number, field: keyof ColumnMapping, value: string) => {
    setColumnMappings((prev) =>
      prev.map((m, i) => (i === index ? { ...m, [field]: value } : m)),
    );
  }, []);

  const handleAutoPopulate = useCallback(() => {
    const newMappings = properties.map((p) => ({
      property_api_name: p.api_name,
      column_name: p.physical_column ?? p.api_name,
    }));
    setColumnMappings(newMappings);
  }, [properties]);

  const handleSave = useCallback(async () => {
    setSaving(true);
    setError(null);
    try {
      await onSave({
        connection_rid: connectionRid,
        schema_name: schemaName,
        table_name: tableName,
        column_mappings: columnMappings,
      });
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to save asset mapping");
    } finally {
      setSaving(false);
    }
  }, [connectionRid, schemaName, tableName, columnMappings, onSave]);

  return (
    <div className="flex flex-col gap-4">
      <div className="grid max-w-xl gap-4">
        <div className="grid gap-1.5">
          <Label htmlFor="connection_rid">Connection</Label>
          <select
            id="connection_rid"
            value={connectionRid}
            onChange={(e) => setConnectionRid(e.target.value)}
            className="flex h-8 w-full rounded-lg border border-input bg-transparent px-2.5 py-1 text-sm transition-colors focus-visible:border-ring focus-visible:ring-3 focus-visible:ring-ring/50"
          >
            <option value="">Select a connection...</option>
            {connections.map((conn) => (
              <option key={conn.rid} value={conn.rid}>
                {conn.display_name} ({conn.connector_type})
              </option>
            ))}
          </select>
        </div>

        <div className="grid gap-1.5">
          <Label htmlFor="schema_name">Schema Name</Label>
          <Input
            id="schema_name"
            value={schemaName}
            onChange={(e) => setSchemaName(e.target.value)}
            placeholder="e.g. public"
          />
        </div>

        <div className="grid gap-1.5">
          <Label htmlFor="table_name">Table Name</Label>
          <Input
            id="table_name"
            value={tableName}
            onChange={(e) => setTableName(e.target.value)}
            placeholder="e.g. users"
          />
        </div>
      </div>

      <div>
        <div className="mb-2 flex items-center justify-between">
          <Label>Column Mappings</Label>
          <div className="flex gap-2">
            {properties.length > 0 && (
              <Button variant="outline" size="sm" onClick={handleAutoPopulate}>
                Auto-populate from properties
              </Button>
            )}
            <Button variant="outline" size="sm" onClick={handleAddMapping}>
              <Plus className="size-4" />
              Add Mapping
            </Button>
          </div>
        </div>

        {columnMappings.length === 0 ? (
          <p className="text-sm text-muted-foreground">No column mappings defined. Click &quot;Add Mapping&quot; to start.</p>
        ) : (
          <div className="rounded-md border">
            <div className="grid grid-cols-[1fr_1fr_auto] gap-2 border-b bg-muted/50 p-2 text-xs font-medium text-muted-foreground">
              <span>Property API Name</span>
              <span>Physical Column</span>
              <span />
            </div>
            {columnMappings.map((mapping, index) => (
              <div key={index} className="grid grid-cols-[1fr_1fr_auto] gap-2 border-b p-2 last:border-b-0">
                <Input
                  value={mapping.property_api_name}
                  onChange={(e) => handleUpdateMapping(index, "property_api_name", e.target.value)}
                  placeholder="property_api_name"
                />
                <Input
                  value={mapping.column_name}
                  onChange={(e) => handleUpdateMapping(index, "column_name", e.target.value)}
                  placeholder="column_name"
                />
                <Button
                  variant="ghost"
                  size="icon-sm"
                  onClick={() => handleRemoveMapping(index)}
                >
                  <X className="size-4" />
                </Button>
              </div>
            ))}
          </div>
        )}
      </div>

      {error && (
        <p className="text-sm text-destructive">{error}</p>
      )}

      <div className="flex justify-end">
        <Button onClick={handleSave} disabled={saving}>
          <Save className="size-4" />
          {saving ? "Saving..." : "Save Mapping"}
        </Button>
      </div>
    </div>
  );
}
