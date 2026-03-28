"use client";

import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { dataApi } from "@/lib/api/data";
import {
  Card,
  CardHeader,
  CardTitle,
  CardContent,
  CardFooter,
} from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";
import { GitBranch, Plus, Trash2, Merge, X } from "lucide-react";

interface Branch {
  name: string;
  hash: string;
}

export default function DataVersionsPage() {
  const queryClient = useQueryClient();
  const [showCreate, setShowCreate] = useState(false);
  const [newName, setNewName] = useState("");
  const [fromRef, setFromRef] = useState("main");
  const [mergeSource, setMergeSource] = useState<string | null>(null);

  const { data, isLoading } = useQuery({
    queryKey: ["data", "branches"],
    queryFn: () => dataApi.listBranches(),
  });

  const branches: Branch[] = (data?.data as unknown as Branch[]) ?? [];

  const createMutation = useMutation({
    mutationFn: () => dataApi.createBranch(newName, fromRef),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["data", "branches"] });
      setShowCreate(false);
      setNewName("");
      setFromRef("main");
    },
  });

  const deleteMutation = useMutation({
    mutationFn: (name: string) => dataApi.deleteBranch(name),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["data", "branches"] });
    },
  });

  const mergeMutation = useMutation({
    mutationFn: (source: string) => dataApi.mergeBranch(source, "main"),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["data", "branches"] });
      setMergeSource(null);
    },
  });

  return (
    <div className="flex flex-col gap-4">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-lg font-semibold">Data Versions</h1>
          <p className="text-sm text-muted-foreground">
            Branch and version management for data
          </p>
        </div>
        <Button onClick={() => setShowCreate(true)} disabled={showCreate}>
          <Plus className="size-4" />
          New Branch
        </Button>
      </div>

      {showCreate && (
        <Card>
          <CardHeader>
            <CardTitle className="text-sm">Create Branch</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="flex gap-3 items-end">
              <div className="flex flex-col gap-1.5 flex-1">
                <label className="text-xs text-muted-foreground">
                  Branch Name
                </label>
                <Input
                  value={newName}
                  onChange={(e) => setNewName(e.target.value)}
                  placeholder="feature/my-branch"
                />
              </div>
              <div className="flex flex-col gap-1.5 w-48">
                <label className="text-xs text-muted-foreground">
                  From Reference
                </label>
                <Input
                  value={fromRef}
                  onChange={(e) => setFromRef(e.target.value)}
                  placeholder="main"
                />
              </div>
            </div>
          </CardContent>
          <CardFooter className="flex gap-2 justify-end">
            <Button
              variant="ghost"
              size="sm"
              onClick={() => setShowCreate(false)}
            >
              <X className="size-4" />
              Cancel
            </Button>
            <Button
              size="sm"
              disabled={!newName.trim() || createMutation.isPending}
              onClick={() => createMutation.mutate()}
            >
              <Plus className="size-4" />
              {createMutation.isPending ? "Creating..." : "Create"}
            </Button>
          </CardFooter>
        </Card>
      )}

      {mergeSource && (
        <Card className="border-amber-500/50">
          <CardContent className="py-3">
            <div className="flex items-center justify-between">
              <p className="text-sm">
                Merge <Badge variant="secondary">{mergeSource}</Badge> into{" "}
                <Badge variant="default">main</Badge>?
              </p>
              <div className="flex gap-2">
                <Button
                  variant="ghost"
                  size="sm"
                  onClick={() => setMergeSource(null)}
                >
                  Cancel
                </Button>
                <Button
                  size="sm"
                  disabled={mergeMutation.isPending}
                  onClick={() => mergeMutation.mutate(mergeSource)}
                >
                  {mergeMutation.isPending ? "Merging..." : "Confirm Merge"}
                </Button>
              </div>
            </div>
          </CardContent>
        </Card>
      )}

      {isLoading ? (
        <div className="flex items-center justify-center py-12">
          <div className="size-6 animate-spin rounded-full border-2 border-primary border-t-transparent" />
        </div>
      ) : branches.length === 0 ? (
        <Card>
          <CardContent className="py-12">
            <div className="flex flex-col items-center gap-2 text-muted-foreground">
              <GitBranch className="size-8" />
              <p className="text-sm">No branches found</p>
            </div>
          </CardContent>
        </Card>
      ) : (
        <div className="flex flex-col gap-2">
          {branches.map((branch) => (
            <Card key={branch.name}>
              <CardContent className="py-3">
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-3">
                    <GitBranch className="size-4 text-muted-foreground" />
                    <span className="font-medium text-sm">{branch.name}</span>
                    {branch.name === "main" && (
                      <Badge variant="default">default</Badge>
                    )}
                    <span className="text-xs text-muted-foreground font-mono">
                      {branch.hash.slice(0, 8)}
                    </span>
                  </div>
                  {branch.name !== "main" && (
                    <div className="flex gap-1">
                      <Button
                        variant="ghost"
                        size="icon-sm"
                        onClick={() => setMergeSource(branch.name)}
                        title="Merge into main"
                      >
                        <Merge className="size-4" />
                      </Button>
                      <Button
                        variant="ghost"
                        size="icon-sm"
                        onClick={() => deleteMutation.mutate(branch.name)}
                        disabled={deleteMutation.isPending}
                        title="Delete branch"
                      >
                        <Trash2 className="size-4 text-destructive" />
                      </Button>
                    </div>
                  )}
                </div>
              </CardContent>
            </Card>
          ))}
        </div>
      )}
    </div>
  );
}
