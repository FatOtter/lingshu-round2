"use client";

import { useState, useEffect, useCallback } from "react";
import { useParams, useRouter } from "next/navigation";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { settingApi } from "@/lib/api/setting";
import type { TenantMember } from "@/types/setting";
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
import { DataTable, type ColumnDef } from "@/components/ui/data-table";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogDescription,
  DialogFooter,
} from "@/components/ui/dialog";
import { ArrowLeft, Save, Trash2, Plus, UserMinus } from "lucide-react";

export default function TenantDetailPage() {
  const params = useParams<{ rid: string }>();
  const router = useRouter();
  const queryClient = useQueryClient();

  const { data, isLoading } = useQuery({
    queryKey: ["setting", "tenant", params.rid],
    queryFn: () => settingApi.getTenant(params.rid),
    enabled: Boolean(params.rid),
  });

  const tenant = data?.data;

  const [displayName, setDisplayName] = useState("");
  const [status, setStatus] = useState<string>("active");

  useEffect(() => {
    if (tenant) {
      setDisplayName(tenant.display_name);
      setStatus(tenant.status);
    }
  }, [tenant]);

  const updateMutation = useMutation({
    mutationFn: () =>
      settingApi.updateTenant(params.rid, {
        display_name: displayName,
        status,
      }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["setting", "tenants"] });
      queryClient.invalidateQueries({
        queryKey: ["setting", "tenant", params.rid],
      });
    },
  });

  const deleteMutation = useMutation({
    mutationFn: () => settingApi.deleteTenant(params.rid),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["setting", "tenants"] });
      router.push("/setting/tenants");
    },
  });

  // Members
  const [membersPage, setMembersPage] = useState(1);
  const membersPageSize = 20;

  const { data: membersData, isLoading: membersLoading } = useQuery({
    queryKey: ["setting", "tenant", params.rid, "members", membersPage],
    queryFn: () =>
      settingApi.queryMembers(params.rid, {
        pagination: { page: membersPage, page_size: membersPageSize },
      }),
    enabled: Boolean(params.rid),
  });

  const members = membersData?.data ?? [];
  const membersTotal = membersData?.pagination?.total ?? 0;

  // Add member dialog
  const [addDialogOpen, setAddDialogOpen] = useState(false);
  const [newMemberUserRid, setNewMemberUserRid] = useState("");
  const [newMemberRole, setNewMemberRole] = useState("member");

  const addMemberMutation = useMutation({
    mutationFn: () =>
      settingApi.addMember(params.rid, {
        user_rid: newMemberUserRid,
        role: newMemberRole,
      }),
    onSuccess: () => {
      queryClient.invalidateQueries({
        queryKey: ["setting", "tenant", params.rid, "members"],
      });
      setAddDialogOpen(false);
      setNewMemberUserRid("");
      setNewMemberRole("member");
    },
  });

  const updateRoleMutation = useMutation({
    mutationFn: ({ userRid, role }: { userRid: string; role: string }) =>
      settingApi.updateMemberRole(params.rid, userRid, role),
    onSuccess: () => {
      queryClient.invalidateQueries({
        queryKey: ["setting", "tenant", params.rid, "members"],
      });
    },
  });

  const removeMemberMutation = useMutation({
    mutationFn: (userRid: string) =>
      settingApi.removeMember(params.rid, userRid),
    onSuccess: () => {
      queryClient.invalidateQueries({
        queryKey: ["setting", "tenant", params.rid, "members"],
      });
    },
  });

  const handleRoleChange = useCallback(
    (userRid: string, role: string) => {
      updateRoleMutation.mutate({ userRid, role });
    },
    [updateRoleMutation],
  );

  const handleRemoveMember = useCallback(
    (userRid: string) => {
      removeMemberMutation.mutate(userRid);
    },
    [removeMemberMutation],
  );

  const memberColumns: ColumnDef<TenantMember>[] = [
    {
      key: "display_name",
      label: "Name",
    },
    {
      key: "email",
      label: "Email",
    },
    {
      key: "role",
      label: "Role",
      render: (value, row) => {
        const member = row as TenantMember;
        return (
          <Select
            value={value as string}
            onValueChange={(v) => handleRoleChange(member.user_rid, v ?? "member")}
          >
            <SelectTrigger size="sm" className="w-28">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="admin">Admin</SelectItem>
              <SelectItem value="member">Member</SelectItem>
              <SelectItem value="viewer">Viewer</SelectItem>
            </SelectContent>
          </Select>
        );
      },
    },
    {
      key: "is_default",
      label: "Default",
      render: (value) => {
        const isDefault = value as boolean;
        return isDefault ? <Badge variant="secondary">Default</Badge> : null;
      },
    },
    {
      key: "user_rid",
      label: "",
      render: (value) => {
        const userRid = value as string;
        return (
          <Button
            variant="ghost"
            size="icon-sm"
            onClick={(e) => {
              e.stopPropagation();
              handleRemoveMember(userRid);
            }}
          >
            <UserMinus className="size-4 text-destructive" />
          </Button>
        );
      },
      className: "w-10",
    },
  ];

  if (isLoading) {
    return (
      <div className="flex items-center justify-center py-12">
        <div className="size-6 animate-spin rounded-full border-2 border-primary border-t-transparent" />
      </div>
    );
  }

  if (!tenant) {
    return (
      <div className="flex flex-col items-center gap-2 py-12">
        <p className="text-sm text-muted-foreground">Tenant not found</p>
        <Button variant="ghost" onClick={() => router.push("/setting/tenants")}>
          <ArrowLeft className="size-4" />
          Back to Tenants
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
          onClick={() => router.push("/setting/tenants")}
        >
          <ArrowLeft className="size-4" />
        </Button>
        <div>
          <h1 className="text-lg font-semibold">{tenant.display_name}</h1>
          <p className="text-sm text-muted-foreground">Tenant: {tenant.rid}</p>
        </div>
      </div>

      <Card>
        <CardHeader>
          <CardTitle>Tenant Details</CardTitle>
          <CardDescription>Update tenant information and status</CardDescription>
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
              <Label>Status</Label>
              <Select
                value={status}
                onValueChange={(val) => setStatus(val ?? "active")}
              >
                <SelectTrigger className="w-full">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="active">
                    <Badge variant="default">Active</Badge>
                  </SelectItem>
                  <SelectItem value="disabled">
                    <Badge variant="outline">Disabled</Badge>
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
            {deleteMutation.isPending ? "Deleting..." : "Delete Tenant"}
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

      <Card>
        <CardHeader>
          <div className="flex items-center justify-between">
            <div>
              <CardTitle>Members</CardTitle>
              <CardDescription>Manage tenant members and their roles</CardDescription>
            </div>
            <Button onClick={() => setAddDialogOpen(true)}>
              <Plus className="size-4" />
              Add Member
            </Button>
          </div>
        </CardHeader>
        <CardContent>
          <DataTable
            columns={memberColumns}
            data={members}
            total={membersTotal}
            page={membersPage}
            pageSize={membersPageSize}
            onPageChange={setMembersPage}
            loading={membersLoading}
            emptyMessage="No members found"
          />
        </CardContent>
      </Card>

      <Dialog open={addDialogOpen} onOpenChange={setAddDialogOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Add Member</DialogTitle>
            <DialogDescription>
              Add a user to this tenant by their user ID.
            </DialogDescription>
          </DialogHeader>
          <div className="flex flex-col gap-4">
            <div className="flex flex-col gap-1.5">
              <Label htmlFor="user_rid">User ID</Label>
              <Input
                id="user_rid"
                placeholder="Enter user RID"
                value={newMemberUserRid}
                onChange={(e) => setNewMemberUserRid(e.target.value)}
              />
            </div>
            <div className="flex flex-col gap-1.5">
              <Label>Role</Label>
              <Select
                value={newMemberRole}
                onValueChange={(v) => setNewMemberRole(v ?? "member")}
              >
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
          </div>
          <DialogFooter>
            <Button
              onClick={() => addMemberMutation.mutate()}
              disabled={!newMemberUserRid.trim() || addMemberMutation.isPending}
            >
              {addMemberMutation.isPending ? "Adding..." : "Add Member"}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}
