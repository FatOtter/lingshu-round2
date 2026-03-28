"use client";

import { useState, useCallback, useEffect } from "react";
import { Button } from "@/components/ui/button";
import { Save } from "lucide-react";

interface ExecutionConfigEditorProps {
  initialValue: Record<string, unknown>;
  onSave: (config: Record<string, unknown>) => Promise<void>;
  disabled?: boolean;
}

export function ExecutionConfigEditor({
  initialValue,
  onSave,
  disabled = false,
}: ExecutionConfigEditorProps) {
  const [jsonText, setJsonText] = useState(() =>
    JSON.stringify(initialValue, null, 2),
  );
  const [validationError, setValidationError] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);
  const [saveError, setSaveError] = useState<string | null>(null);

  useEffect(() => {
    setJsonText(JSON.stringify(initialValue, null, 2));
  }, [initialValue]);

  const handleChange = useCallback((value: string) => {
    setJsonText(value);
    setValidationError(null);
    setSaveError(null);
    try {
      JSON.parse(value);
    } catch (err) {
      setValidationError(err instanceof SyntaxError ? err.message : "Invalid JSON");
    }
  }, []);

  const handleSave = useCallback(async () => {
    setSaveError(null);
    let parsed: Record<string, unknown>;
    try {
      parsed = JSON.parse(jsonText) as Record<string, unknown>;
    } catch (err) {
      setValidationError(err instanceof SyntaxError ? err.message : "Invalid JSON");
      return;
    }

    setSaving(true);
    try {
      await onSave(parsed);
    } catch (err) {
      setSaveError(err instanceof Error ? err.message : "Failed to save execution config");
    } finally {
      setSaving(false);
    }
  }, [jsonText, onSave]);

  const handleFormat = useCallback(() => {
    try {
      const parsed = JSON.parse(jsonText);
      setJsonText(JSON.stringify(parsed, null, 2));
      setValidationError(null);
    } catch (err) {
      setValidationError(err instanceof SyntaxError ? err.message : "Invalid JSON");
    }
  }, [jsonText]);

  if (disabled) {
    return (
      <div className="flex h-48 items-center justify-center rounded-lg border border-dashed text-muted-foreground">
        Save the action type first to edit execution configuration
      </div>
    );
  }

  return (
    <div className="flex flex-col gap-3">
      <p className="text-xs text-muted-foreground">
        Note: Install @monaco-editor/react for a richer editing experience. Using JSON textarea editor as fallback.
      </p>
      <textarea
        value={jsonText}
        onChange={(e) => handleChange(e.target.value)}
        spellCheck={false}
        className="h-64 w-full resize-y rounded-lg border border-input bg-muted p-4 font-mono text-xs leading-relaxed focus-visible:border-ring focus-visible:outline-none focus-visible:ring-3 focus-visible:ring-ring/50"
      />
      {validationError && (
        <p className="text-sm text-destructive">JSON Error: {validationError}</p>
      )}
      {saveError && (
        <p className="text-sm text-destructive">{saveError}</p>
      )}
      <div className="flex justify-end gap-2">
        <Button variant="outline" size="sm" onClick={handleFormat}>
          Format JSON
        </Button>
        <Button
          size="sm"
          onClick={handleSave}
          disabled={saving || !!validationError}
        >
          <Save className="size-4" />
          {saving ? "Saving..." : "Save Config"}
        </Button>
      </div>
    </div>
  );
}
