"use client";

import { useState, useCallback } from "react";
import type { A2UIForm, A2UIFormField } from "@/types/a2ui";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";

interface A2UIFormViewProps {
  data: A2UIForm;
  onSubmit?: (values: Record<string, unknown>) => void;
}

function buildInitialValues(fields: A2UIFormField[]): Record<string, unknown> {
  const values: Record<string, unknown> = {};
  for (const field of fields) {
    if (field.default_value !== undefined) {
      values[field.key] = field.default_value;
    } else if (field.type === "boolean") {
      values[field.key] = false;
    } else if (field.type === "number") {
      values[field.key] = 0;
    } else {
      values[field.key] = "";
    }
  }
  return values;
}

function FormField({
  field,
  value,
  onChange,
}: {
  field: A2UIFormField;
  value: unknown;
  onChange: (key: string, value: unknown) => void;
}) {
  switch (field.type) {
    case "text":
      return (
        <Input
          id={field.key}
          value={(value as string) ?? ""}
          placeholder={field.placeholder}
          onChange={(e) => onChange(field.key, e.target.value)}
        />
      );

    case "number":
      return (
        <Input
          id={field.key}
          type="number"
          value={String(value ?? 0)}
          placeholder={field.placeholder}
          onChange={(e) => onChange(field.key, Number(e.target.value))}
        />
      );

    case "textarea":
      return (
        <Textarea
          id={field.key}
          value={(value as string) ?? ""}
          placeholder={field.placeholder}
          onChange={(e) => onChange(field.key, e.target.value)}
          rows={3}
        />
      );

    case "select":
      return (
        <Select
          value={(value as string) ?? ""}
          onValueChange={(v) => onChange(field.key, v ?? "")}
        >
          <SelectTrigger className="w-full">
            <SelectValue placeholder={field.placeholder ?? "Select..."} />
          </SelectTrigger>
          <SelectContent>
            {(field.options ?? []).map((opt) => (
              <SelectItem key={opt.value} value={opt.value}>
                {opt.label}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
      );

    case "boolean":
      return (
        <label className="flex items-center gap-2 cursor-pointer">
          <input
            type="checkbox"
            checked={Boolean(value)}
            onChange={(e) => onChange(field.key, e.target.checked)}
            className="size-4 rounded border border-input accent-primary"
          />
          <span className="text-sm">{field.label}</span>
        </label>
      );

    default:
      return null;
  }
}

export function A2UIFormView({ data, onSubmit }: A2UIFormViewProps) {
  const [values, setValues] = useState<Record<string, unknown>>(() =>
    buildInitialValues(data.fields),
  );

  const handleChange = useCallback((key: string, value: unknown) => {
    setValues((prev) => ({ ...prev, [key]: value }));
  }, []);

  const handleSubmit = useCallback(
    (e: React.FormEvent) => {
      e.preventDefault();
      onSubmit?.(values);
    },
    [values, onSubmit],
  );

  return (
    <div className="my-2 rounded-md border p-4">
      <form onSubmit={handleSubmit} className="flex flex-col gap-3">
        <div>
          <h3 className="text-sm font-medium">{data.title}</h3>
          {data.description && (
            <p className="text-xs text-muted-foreground mt-0.5">{data.description}</p>
          )}
        </div>

        {data.fields.map((field) => (
          <div key={field.key} className="flex flex-col gap-1.5">
            {field.type !== "boolean" && (
              <Label htmlFor={field.key}>
                {field.label}
                {field.required && <span className="text-destructive ml-0.5">*</span>}
              </Label>
            )}
            <FormField
              field={field}
              value={values[field.key]}
              onChange={handleChange}
            />
          </div>
        ))}

        <div className="flex justify-end pt-1">
          <Button type="submit" size="sm">
            {data.submit_label ?? "Submit"}
          </Button>
        </div>
      </form>
    </div>
  );
}
