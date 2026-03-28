export interface User {
  rid: string;
  email: string;
  display_name: string;
  role: "admin" | "member" | "viewer";
  is_active: boolean;
  created_at: string;
  last_login_at: string | null;
}

export interface Tenant {
  rid: string;
  display_name: string;
  status: "active" | "disabled";
  config: Record<string, unknown> | null;
  created_at: string;
  updated_at: string;
}

export interface TenantMember {
  user_rid: string;
  display_name: string;
  email: string;
  role: "admin" | "member" | "viewer";
  is_default: boolean;
  created_at: string;
}

export interface AuditLog {
  log_id: string;
  tenant_id: string;
  user_id: string;
  module: string;
  action: string;
  resource_type: string;
  resource_rid: string | null;
  details: Record<string, unknown>;
  created_at: string;
}

export interface LoginRequest {
  email: string;
  password: string;
}

export interface LoginResponse {
  user: User;
  access_token: string;
  expires_at: string;
}
