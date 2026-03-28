"use client";

import { useState, useEffect } from "react";
import { useParams, useRouter } from "next/navigation";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { settingApi } from "@/lib/api/setting";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import {
  Card,
  CardHeader,
  CardTitle,
  CardDescription,
  CardContent,
  CardFooter,
} from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { ArrowLeft, Save, Trash2 } from "lucide-react";

export default function UserDetailPage() {
  const params = useParams<{ rid: string }>();
  const router = useRouter();
  const queryClient = useQueryClient();

  const { data, isLoading } = useQuery({
    queryKey: ["setting", "user", params.rid],
    queryFn: () => settingApi.getUser(params.rid),
    enabled: Boolean(params.rid),
  });

  const user = data?.data;

  const [displayName, setDisplayName] = useState("");
  const [email, setEmail] = useState("");
  const [role, setRole] = useState<string>("member");
  const [isActive, setIsActive] = useState(true);

  useEffect(() => {
    if (user) {
      setDisplayName(user.display_name);
      setEmail(user.email);
      setRole(user.role);
      setIsActive(user.is_active);
    }
  }, [user]);

  const updateMutation = useMutation({
    mutationFn: () =>
      settingApi.updateUser(params.rid, {
        display_name: displayName,
        role,
        is_active: isActive,
      }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["setting", "users"] });
      queryClient.invalidateQueries({
        queryKey: ["setting", "user", params.rid],
      });
    },
  });

  const deleteMutation = useMutation({
    mutationFn: () => settingApi.deleteUser(params.rid),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["setting", "users"] });
      router.push("/setting/users");
    },
  });

  if (isLoading) {
    return (
      <div className="flex items-center justify-center py-12">
        <div className="size-6 animate-spin rounded-full border-2 border-primary border-t-transparent" />
      </div>
    );
  }

  if (!user) {
    return (
      <div className="flex flex-col items-center gap-2 py-12">
        <p className="text-sm text-muted-foreground">User not found</p>
        <Button variant="ghost" onClick={() => router.push("/setting/users")}>
          <ArrowLeft className="size-4" />
          Back to Users
        </Button>
      </div>
    );
  }

  return (
    <div className="flex flex-col gap-4">
      <div className="flex items-center gap-2">
        <Button
          variant="ghost"
          size="icon-sm"
          onClick={() => router.push("/setting/users")}
        >
          <ArrowLeft className="size-4" />
        </Button>
        <div>
          <h1 className="text-lg font-semibold">{user.display_name}</h1>
          <p className="text-sm text-muted-foreground">{user.email}</p>
        </div>
      </div>

      <Card>
        <CardHeader>
          <CardTitle>User Details</CardTitle>
          <CardDescription>Update user information and permissions</CardDescription>
        </CardHeader>
        <CardContent>
          <div className="flex flex-col gap-4 max-w-md">
            <div className="flex flex-col gap-1.5">
              <Label htmlFor="display_name">Display Name</Label>
              <Input
                id="display_name"
                value={displayName}
                onChange={(e) => setDisplayName(e.target.value)}
              />
            </div>

            <div className="flex flex-col gap-1.5">
              <Label htmlFor="email">Email</Label>
              <Input id="email" value={email} disabled />
            </div>

            <div className="flex flex-col gap-1.5">
              <Label>Role</Label>
              <Select value={role} onValueChange={(v) => setRole(v ?? "member")}>
                <SelectTrigger className="w-full">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="admin">Admin</SelectItem>
                  <SelectItem value="member">Member</SelectItem>
                  <SelectItem value="viewer">Viewer</SelectItem>
                </SelectContent>
              </Select>
            </div>

            <div className="flex flex-col gap-1.5">
              <Label>Status</Label>
              <Select
                value={isActive ? "active" : "inactive"}
                onValueChange={(val) => setIsActive(val === "active")}
              >
                <SelectTrigger className="w-full">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="active">
                    <Badge variant="default">Active</Badge>
                  </SelectItem>
                  <SelectItem value="inactive">
                    <Badge variant="outline">Inactive</Badge>
                  </SelectItem>
                </SelectContent>
              </Select>
            </div>
          </div>
        </CardContent>
        <CardFooter className="flex justify-between">
          <Button
            variant="destructive"
            onClick={() => deleteMutation.mutate()}
            disabled={deleteMutation.isPending}
          >
            <Trash2 className="size-4" />
            {deleteMutation.isPending ? "Deleting..." : "Delete User"}
          </Button>
          <Button
            onClick={() => updateMutation.mutate()}
            disabled={updateMutation.isPending}
          >
            <Save className="size-4" />
            {updateMutation.isPending ? "Saving..." : "Save Changes"}
          </Button>
        </CardFooter>
      </Card>
    </div>
  );
}
