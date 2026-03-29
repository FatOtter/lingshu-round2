import type { ApiResponse, PagedResponse } from "./client";
import { apiClient } from "./client";
import type {
  ObjectType,
  LinkType,
  InterfaceType,
  ActionType,
  SharedPropertyType,
  TopologyData,
  StagingSummary,
  Snapshot,
} from "@/types/ontology";

const PREFIX = "/ontology/v1";

export const ontologyApi = {
  // ObjectType
  queryObjectTypes: (params?: { pagination?: { page: number; page_size: number }; search?: string; lifecycle_status?: string }) =>
    apiClient.post<PagedResponse<ObjectType>>(`${PREFIX}/object-types/query`, params),
  getObjectType: (rid: string, branch?: string) =>
    apiClient.get<ApiResponse<ObjectType>>(`${PREFIX}/object-types/${rid}${branch ? `?branch=${branch}` : ""}`),
  getObjectTypeDraft: (rid: string) =>
    apiClient.get<ApiResponse<ObjectType>>(`${PREFIX}/object-types/${rid}/draft`),
  createObjectType: (data: Record<string, unknown>) =>
    apiClient.post<ApiResponse<ObjectType>>(`${PREFIX}/object-types`, data),
  updateObjectType: (rid: string, data: Record<string, unknown>) =>
    apiClient.put<ApiResponse<ObjectType>>(`${PREFIX}/object-types/${rid}`, data),
  deleteObjectType: (rid: string) =>
    apiClient.delete<ApiResponse<null>>(`${PREFIX}/object-types/${rid}`),

  // LinkType
  queryLinkTypes: (params?: { pagination?: { page: number; page_size: number }; search?: string }) =>
    apiClient.post<PagedResponse<LinkType>>(`${PREFIX}/link-types/query`, params),
  getLinkType: (rid: string, branch?: string) =>
    apiClient.get<ApiResponse<LinkType>>(`${PREFIX}/link-types/${rid}${branch ? `?branch=${branch}` : ""}`),
  createLinkType: (data: Record<string, unknown>) =>
    apiClient.post<ApiResponse<LinkType>>(`${PREFIX}/link-types`, data),
  updateLinkType: (rid: string, data: Record<string, unknown>) =>
    apiClient.put<ApiResponse<LinkType>>(`${PREFIX}/link-types/${rid}`, data),
  deleteLinkType: (rid: string) =>
    apiClient.delete<ApiResponse<null>>(`${PREFIX}/link-types/${rid}`),

  // InterfaceType
  queryInterfaceTypes: (params?: { pagination?: { page: number; page_size: number }; search?: string }) =>
    apiClient.post<PagedResponse<InterfaceType>>(`${PREFIX}/interface-types/query`, params),
  getInterfaceType: (rid: string) =>
    apiClient.get<ApiResponse<InterfaceType>>(`${PREFIX}/interface-types/${rid}`),
  createInterfaceType: (data: Record<string, unknown>) =>
    apiClient.post<ApiResponse<InterfaceType>>(`${PREFIX}/interface-types`, data),
  updateInterfaceType: (rid: string, data: Record<string, unknown>) =>
    apiClient.put<ApiResponse<InterfaceType>>(`${PREFIX}/interface-types/${rid}`, data),
  deleteInterfaceType: (rid: string) =>
    apiClient.delete<ApiResponse<null>>(`${PREFIX}/interface-types/${rid}`),

  // ActionType
  queryActionTypes: (params?: { pagination?: { page: number; page_size: number }; search?: string }) =>
    apiClient.post<PagedResponse<ActionType>>(`${PREFIX}/action-types/query`, params),
  getActionType: (rid: string) =>
    apiClient.get<ApiResponse<ActionType>>(`${PREFIX}/action-types/${rid}`),
  createActionType: (data: Record<string, unknown>) =>
    apiClient.post<ApiResponse<ActionType>>(`${PREFIX}/action-types`, data),
  updateActionType: (rid: string, data: Record<string, unknown>) =>
    apiClient.put<ApiResponse<ActionType>>(`${PREFIX}/action-types/${rid}`, data),
  deleteActionType: (rid: string) =>
    apiClient.delete<ApiResponse<null>>(`${PREFIX}/action-types/${rid}`),

  // SharedPropertyType
  querySharedPropertyTypes: (params?: { pagination?: { page: number; page_size: number }; search?: string }) =>
    apiClient.post<PagedResponse<SharedPropertyType>>(`${PREFIX}/shared-property-types/query`, params),
  getSharedPropertyType: (rid: string) =>
    apiClient.get<ApiResponse<SharedPropertyType>>(`${PREFIX}/shared-property-types/${rid}`),
  createSharedPropertyType: (data: Record<string, unknown>) =>
    apiClient.post<ApiResponse<SharedPropertyType>>(`${PREFIX}/shared-property-types`, data),
  updateSharedPropertyType: (rid: string, data: Record<string, unknown>) =>
    apiClient.put<ApiResponse<SharedPropertyType>>(`${PREFIX}/shared-property-types/${rid}`, data),
  deleteSharedPropertyType: (rid: string) =>
    apiClient.delete<ApiResponse<null>>(`${PREFIX}/shared-property-types/${rid}`),

  // Edit lock
  acquireLock: (entityType: string, rid: string) =>
    apiClient.post<ApiResponse<{ lock_token: string }>>(`${PREFIX}/${entityType}/${rid}/lock`),
  releaseLock: (entityType: string, rid: string) =>
    apiClient.delete<ApiResponse<null>>(`${PREFIX}/${entityType}/${rid}/lock`),
  heartbeatLock: (entityType: string, rid: string) =>
    apiClient.post<ApiResponse<null>>(`${PREFIX}/${entityType}/${rid}/lock/heartbeat`),

  // Version management
  submitToStaging: (entityType: string, rid: string) =>
    apiClient.post<ApiResponse<null>>(`${PREFIX}/${entityType}/${rid}/submit-to-staging`),
  getStagingSummary: () =>
    apiClient.get<ApiResponse<StagingSummary>>(`${PREFIX}/staging/summary`),
  commitStaging: (commitMessage: string) =>
    apiClient.post<ApiResponse<Snapshot>>(`${PREFIX}/staging/commit`, { commit_message: commitMessage }),
  discardStaging: (rids?: string[]) =>
    apiClient.post<ApiResponse<null>>(`${PREFIX}/staging/discard`, { rids }),

  // Snapshots
  querySnapshots: (params?: { pagination?: { page: number; page_size: number } }) =>
    apiClient.post<PagedResponse<Snapshot>>(`${PREFIX}/snapshots/query`, params),
  getSnapshot: (snapshotId: string) =>
    apiClient.get<ApiResponse<Snapshot>>(`${PREFIX}/snapshots/${snapshotId}`),
  rollbackSnapshot: (snapshotId: string) =>
    apiClient.post<ApiResponse<null>>(`${PREFIX}/snapshots/${snapshotId}/rollback`),

  // Topology + Search
  getTopology: (branch?: string) =>
    apiClient.get<ApiResponse<TopologyData>>(`${PREFIX}/topology${branch ? `?branch=${branch}` : ""}`),
  search: (query: string, params?: { entity_types?: string[]; limit?: number }) =>
    apiClient.post<ApiResponse<{ results: Array<{ type: string; rid: string; api_name: string; display_name: string }> }>>(`${PREFIX}/search`, { query, ...params }),

  // Overview
  getOverview: () =>
    apiClient.get<ApiResponse<Record<string, unknown>>>(`${PREFIX}/overview`),
};
