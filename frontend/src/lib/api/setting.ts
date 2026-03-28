import type { ApiResponse, PagedResponse } from "./client";
import { apiClient } from "./client";
import type { AuditLog, LoginResponse, Tenant, TenantMember, User } from "@/types/setting";

const PREFIX = "/setting/v1";

export const settingApi = {
  login: (email: string, password: string) =>
    apiClient.post<ApiResponse<LoginResponse>>(`${PREFIX}/auth/login`, { email, password }),

  logout: () =>
    apiClient.post<ApiResponse<null>>(`${PREFIX}/auth/logout`),

  // SSO
  ssoConfig: () =>
    apiClient.get<ApiResponse<{ enabled: boolean; provider_name: string | null; authorization_url: string | null }>>(`${PREFIX}/auth/sso/config`),

  ssoCallback: (code: string, state: string) =>
    apiClient.post<ApiResponse<LoginResponse>>(`${PREFIX}/auth/sso/callback`, { code, state }),

  refresh: () =>
    apiClient.post<ApiResponse<{ access_token: string; expires_at: string }>>(`${PREFIX}/auth/refresh`),

  me: () =>
    apiClient.get<ApiResponse<User>>(`${PREFIX}/auth/me`),

  changePassword: (current_password: string, new_password: string) =>
    apiClient.post<ApiResponse<null>>(`${PREFIX}/auth/change-password`, { current_password, new_password }),

  // Users
  getUser: (rid: string) =>
    apiClient.get<ApiResponse<User>>(`${PREFIX}/users/${rid}`),

  queryUsers: (params?: {
    filters?: Array<{ field: string; operator: string; value: unknown }>;
    sort?: Array<{ field: string; order: string }>;
    pagination?: { page: number; page_size: number };
  }) =>
    apiClient.post<PagedResponse<User>>(`${PREFIX}/users/query`, params ?? { pagination: { page: 1, page_size: 20 } }),

  createUser: (data: { email: string; display_name: string; password: string; role?: string }) =>
    apiClient.post<ApiResponse<User>>(`${PREFIX}/users`, data),

  updateUser: (rid: string, data: Partial<{ display_name: string; role: string; is_active: boolean }>) =>
    apiClient.put<ApiResponse<User>>(`${PREFIX}/users/${rid}`, data),

  deleteUser: (rid: string) =>
    apiClient.delete<ApiResponse<null>>(`${PREFIX}/users/${rid}`),

  // Audit logs
  queryAuditLogs: (params?: { module?: string; user_id?: string; pagination?: { page: number; page_size: number } }) =>
    apiClient.post<PagedResponse<AuditLog>>(`${PREFIX}/audit-logs/query`, params ?? { pagination: { page: 1, page_size: 20 } }),

  // Tenants
  createTenant: (data: { display_name: string; config?: Record<string, unknown> }) =>
    apiClient.post<ApiResponse<Tenant>>(`${PREFIX}/tenants`, data),

  queryTenants: (params?: { pagination?: { page: number; page_size: number } }) =>
    apiClient.post<PagedResponse<Tenant>>(`${PREFIX}/tenants/query`, params ?? { pagination: { page: 1, page_size: 20 } }),

  getTenant: (rid: string) =>
    apiClient.get<ApiResponse<Tenant>>(`${PREFIX}/tenants/${rid}`),

  updateTenant: (rid: string, data: Partial<{ display_name: string; status: string; config: Record<string, unknown> }>) =>
    apiClient.put<ApiResponse<Tenant>>(`${PREFIX}/tenants/${rid}`, data),

  deleteTenant: (rid: string) =>
    apiClient.delete<ApiResponse<null>>(`${PREFIX}/tenants/${rid}`),

  switchTenant: (tenant_rid: string) =>
    apiClient.post<ApiResponse<{ user: User }>>(`${PREFIX}/tenants/switch`, { tenant_rid }),

  // Members
  queryMembers: (tenantRid: string, params?: { pagination?: { page: number; page_size: number } }) =>
    apiClient.post<PagedResponse<TenantMember>>(`${PREFIX}/tenants/${tenantRid}/members/query`, params ?? { pagination: { page: 1, page_size: 20 } }),

  addMember: (tenantRid: string, data: { user_rid: string; role?: string }) =>
    apiClient.post<ApiResponse<TenantMember>>(`${PREFIX}/tenants/${tenantRid}/members`, data),

  updateMemberRole: (tenantRid: string, userRid: string, role: string) =>
    apiClient.put<ApiResponse<TenantMember>>(`${PREFIX}/tenants/${tenantRid}/members/${userRid}`, { role }),

  removeMember: (tenantRid: string, userRid: string) =>
    apiClient.delete<ApiResponse<null>>(`${PREFIX}/tenants/${tenantRid}/members/${userRid}`),
};
