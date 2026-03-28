import type { ApiResponse, PagedResponse } from "./client";
import { apiClient } from "./client";
import type { Connection, QueryResult, SchemaMetadata } from "@/types/data";

const PREFIX = "/data/v1";

export const dataApi = {
  // Connections
  queryConnections: (params?: { pagination?: { page: number; page_size: number } }) =>
    apiClient.post<PagedResponse<Connection>>(`${PREFIX}/connections/query`, params ?? { pagination: { page: 1, page_size: 20 } }),
  getConnection: (rid: string) =>
    apiClient.get<ApiResponse<Connection>>(`${PREFIX}/connections/${rid}`),
  createConnection: (data: Record<string, unknown>) =>
    apiClient.post<ApiResponse<Connection>>(`${PREFIX}/connections`, data),
  updateConnection: (rid: string, data: Record<string, unknown>) =>
    apiClient.put<ApiResponse<Connection>>(`${PREFIX}/connections/${rid}`, data),
  deleteConnection: (rid: string) =>
    apiClient.delete<ApiResponse<null>>(`${PREFIX}/connections/${rid}`),
  testConnection: (rid: string) =>
    apiClient.post<ApiResponse<{ success: boolean; message: string }>>(`${PREFIX}/connections/${rid}/test`),

  // Instances
  queryInstances: (typeKind: string, typeRid: string, params?: Record<string, unknown>) =>
    apiClient.post<ApiResponse<QueryResult>>(`${PREFIX}/${typeKind}/${typeRid}/instances/query`, params),
  getInstance: (typeKind: string, typeRid: string, primaryKey: string) =>
    apiClient.get<ApiResponse<{ fields: Record<string, unknown> }>>(`${PREFIX}/${typeKind}/${typeRid}/instances/${primaryKey}`),
  getSchema: (typeKind: string, typeRid: string) =>
    apiClient.get<ApiResponse<SchemaMetadata>>(`${PREFIX}/${typeKind}/${typeRid}/schema`),

  // Relations
  getInstanceLinks: (objectTypeRid: string, primaryKey: string, params?: Record<string, unknown>) =>
    apiClient.post<ApiResponse<QueryResult>>(`${PREFIX}/objects/${objectTypeRid}/instances/${primaryKey}/links`, params),

  // Branches
  listBranches: () =>
    apiClient.get<ApiResponse<Array<{ name: string; hash: string }>>>(`${PREFIX}/branches`),
  getBranch: (name: string) =>
    apiClient.get<ApiResponse<{ name: string; hash: string }>>(`${PREFIX}/branches/${name}`),
  createBranch: (name: string, fromRef?: string) =>
    apiClient.post<ApiResponse<{ name: string; hash: string }>>(`${PREFIX}/branches`, { name, from_ref: fromRef ?? "main" }),
  deleteBranch: (name: string) =>
    apiClient.delete<ApiResponse<null>>(`${PREFIX}/branches/${name}`),
  mergeBranch: (source: string, target?: string) =>
    apiClient.post<ApiResponse<Record<string, unknown>>>(`${PREFIX}/branches/${source}/merge`, { target: target ?? "main" }),
  diffBranches: (fromRef: string, toRef: string) =>
    apiClient.get<ApiResponse<Record<string, unknown>[]>>(`${PREFIX}/branches/${fromRef}/diff/${toRef}`),

  // Overview
  getOverview: () =>
    apiClient.get<ApiResponse<Record<string, unknown>>>(`${PREFIX}/overview`),
};
