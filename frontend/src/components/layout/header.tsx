"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { MessageSquare, LogOut, User, Building2 } from "lucide-react";
import { useQuery, useMutation } from "@tanstack/react-query";
import { Button } from "@/components/ui/button";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { useAuth } from "@/hooks/use-auth";
import { useShellStore } from "@/stores/shell-store";
import { settingApi } from "@/lib/api/setting";

const MODULE_LABELS: Record<string, string> = {
  ontology: "Ontology",
  data: "Data",
  function: "Function",
  agent: "Agent",
  setting: "Setting",
};

function Breadcrumb() {
  const pathname = usePathname();
  const segments = pathname.split("/").filter(Boolean);
  const currentModule = segments[0] ?? "";
  const section = segments[1] ?? "";

  return (
    <div className="flex items-center gap-1.5 text-sm text-muted-foreground">
      <span className="font-medium text-foreground">{MODULE_LABELS[currentModule] ?? currentModule}</span>
      {section && (
        <>
          <span>/</span>
          <span className="capitalize">{section.replace(/-/g, " ")}</span>
        </>
      )}
    </div>
  );
}

function TenantSwitcher() {
  const { data: tenantsData } = useQuery({
    queryKey: ["setting", "tenants", "switcher"],
    queryFn: () => settingApi.queryTenants({ pagination: { page: 1, page_size: 100 } }),
  });

  const switchMutation = useMutation({
    mutationFn: (tenantRid: string) => settingApi.switchTenant(tenantRid),
    onSuccess: () => {
      window.location.reload();
    },
  });

  const tenants = tenantsData?.data ?? [];

  if (tenants.length === 0) return null;

  const activeTenants = tenants.filter((t) => t.status === "active");

  return (
    <div className="flex items-center gap-1.5">
      <Building2 className="size-3.5 text-muted-foreground" />
      <Select
        onValueChange={(value) => {
          const tenantRid = String(value ?? "");
          if (tenantRid) {
            switchMutation.mutate(tenantRid);
          }
        }}
      >
        <SelectTrigger size="sm" className="h-7 w-auto max-w-[180px] gap-1 border-dashed text-xs">
          <SelectValue placeholder="Switch tenant" />
        </SelectTrigger>
        <SelectContent>
          {activeTenants.map((tenant) => (
            <SelectItem key={tenant.rid} value={tenant.rid}>
              {tenant.display_name}
            </SelectItem>
          ))}
        </SelectContent>
      </Select>
    </div>
  );
}

export function Header() {
  const { user, logout } = useAuth();
  const pathname = usePathname();
  const isAgentModule = pathname.startsWith("/agent");
  const toggle = useShellStore((s) => s.toggle);

  return (
    <header className="flex h-[50px] items-center justify-between border-b bg-card px-4">
      <div className="flex items-center gap-4">
        <Link href="/" className="text-lg font-bold tracking-tight">
          LingShu
        </Link>
        <Breadcrumb />
      </div>

      <div className="flex items-center gap-2">
        <TenantSwitcher />

        {!isAgentModule && (
          <Button variant="ghost" size="icon" onClick={toggle} aria-label="Toggle Copilot Shell">
            <MessageSquare className="size-4" />
          </Button>
        )}

        <DropdownMenu>
          <DropdownMenuTrigger
            render={
              <Button variant="ghost" size="icon" className="rounded-full" />
            }
          >
            <User className="size-4" />
          </DropdownMenuTrigger>
          <DropdownMenuContent align="end" className="w-48">
            <div className="px-2 py-1.5 text-sm">
              <p className="font-medium">{user?.display_name ?? "User"}</p>
              <p className="text-muted-foreground">{user?.email}</p>
            </div>
            <DropdownMenuSeparator />
            <DropdownMenuItem render={<Link href="/setting/users" />}>
              Settings
            </DropdownMenuItem>
            <DropdownMenuSeparator />
            <DropdownMenuItem onClick={logout}>
              <LogOut className="mr-2 size-4" />
              Sign out
            </DropdownMenuItem>
          </DropdownMenuContent>
        </DropdownMenu>
      </div>
    </header>
  );
}
