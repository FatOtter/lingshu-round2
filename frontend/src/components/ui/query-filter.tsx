"use client";

import { useState, useCallback } from "react";
import { Search, X } from "lucide-react";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Badge } from "@/components/ui/badge";
import type { Filter } from "@/types/common";

export interface FilterField {
  key: string;
  label: string;
  type: "text" | "select";
  options?: Array<{ label: string; value: string }>;
}

interface QueryFilterProps {
  fields: FilterField[];
  onSearch: (query: string) => void;
  onFilter: (filters: Filter[]) => void;
  searchPlaceholder?: string;
}

export function QueryFilter({ fields, onSearch, onFilter, searchPlaceholder = "Search..." }: QueryFilterProps) {
  const [query, setQuery] = useState("");
  const [activeFilters, setActiveFilters] = useState<Filter[]>([]);

  const handleSearch = useCallback(() => {
    onSearch(query);
  }, [query, onSearch]);

  const handleQueryChange = useCallback(
    (value: string) => {
      setQuery(value);
      onSearch(value);
    },
    [onSearch],
  );

  const handleFilterChange = useCallback(
    (field: string, value: string) => {
      const updated = activeFilters.filter((f) => f.field !== field);
      if (value && value !== "__all__") {
        updated.push({ field, operator: "eq", value });
      }
      setActiveFilters(updated);
      onFilter(updated);
    },
    [activeFilters, onFilter],
  );

  const removeFilter = useCallback(
    (field: string) => {
      const updated = activeFilters.filter((f) => f.field !== field);
      setActiveFilters(updated);
      onFilter(updated);
    },
    [activeFilters, onFilter],
  );

  return (
    <div className="flex flex-col gap-2">
      <div className="flex items-center gap-2">
        <div className="relative flex-1 max-w-sm">
          <Search className="absolute left-2.5 top-1/2 size-4 -translate-y-1/2 text-muted-foreground" />
          <Input
            placeholder={searchPlaceholder}
            value={query}
            onChange={(e) => handleQueryChange(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && handleSearch()}
            className="pl-8"
          />
        </div>
        {fields
          .filter((f) => f.type === "select")
          .map((field) => (
            <Select
              key={field.key}
              onValueChange={(value) => handleFilterChange(field.key, String(value ?? ""))}
            >
              <SelectTrigger className="w-[160px]">
                <SelectValue placeholder={field.label} />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="__all__">All</SelectItem>
                {field.options?.map((opt) => (
                  <SelectItem key={opt.value} value={opt.value}>
                    {opt.label}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          ))}
      </div>

      {activeFilters.length > 0 && (
        <div className="flex items-center gap-1.5">
          {activeFilters.map((f) => (
            <Badge key={f.field} variant="secondary" className="gap-1">
              {f.field}: {String(f.value ?? "")}
              <button onClick={() => removeFilter(f.field)}>
                <X className="size-3" />
              </button>
            </Badge>
          ))}
          <Button
            variant="ghost"
            size="xs"
            onClick={() => {
              setActiveFilters([]);
              onFilter([]);
            }}
          >
            Clear all
          </Button>
        </div>
      )}
    </div>
  );
}
