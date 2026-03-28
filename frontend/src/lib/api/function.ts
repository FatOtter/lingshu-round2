import type { ApiResponse, PagedResponse } from "./client";
import { apiClient } from "./client";
import type { CapabilityDescriptor, Execution, GlobalFunction, Workflow, WorkflowExecution } from "@/types/function";

const PREFIX = "/function/v1";

export const functionApi = {
  // Actions
  executeAction: (rid: string, params: Record<string, unknown>, options?: { skip_confirmation?: boolean }) =>
    apiClient.post<ApiResponse<Execution>>(`${PREFIX}/actions/${rid}/execute`, { params, ...options }),
  getExecution: (executionId: string) =>
    apiClient.get<ApiResponse<Execution>>(`${PREFIX}/executions/${executionId}`),
  queryExecutions: (params?: { capability_type?: string; status?: string; pagination?: { page: number; page_size: number } }) =>
    apiClient.post<PagedResponse<Execution>>(`${PREFIX}/executions/query`, params ?? { pagination: { page: 1, page_size: 20 } }),
  confirmExecution: (executionId: string) =>
    apiClient.post<ApiResponse<Execution>>(`${PREFIX}/executions/${executionId}/confirm`),
  cancelExecution: (executionId: string) =>
    apiClient.post<ApiResponse<Execution>>(`${PREFIX}/executions/${executionId}/cancel`),

  // Global Functions
  queryFunctions: (params?: { pagination?: { page: number; page_size: number } }) =>
    apiClient.post<PagedResponse<GlobalFunction>>(`${PREFIX}/functions/query`, params ?? { pagination: { page: 1, page_size: 20 } }),
  getFunction: (rid: string) =>
    apiClient.get<ApiResponse<GlobalFunction>>(`${PREFIX}/functions/${rid}`),
  createFunction: (data: Record<string, unknown>) =>
    apiClient.post<ApiResponse<GlobalFunction>>(`${PREFIX}/functions`, data),
  updateFunction: (rid: string, data: Record<string, unknown>) =>
    apiClient.put<ApiResponse<GlobalFunction>>(`${PREFIX}/functions/${rid}`, data),
  deleteFunction: (rid: string) =>
    apiClient.delete<ApiResponse<null>>(`${PREFIX}/functions/${rid}`),
  executeFunction: (rid: string, params: Record<string, unknown>) =>
    apiClient.post<ApiResponse<Execution>>(`${PREFIX}/functions/${rid}/execute`, { params }),

  // Capabilities (returns flat list, no pagination)
  queryCapabilities: (params?: { type?: string }) =>
    apiClient.post<ApiResponse<CapabilityDescriptor[]>>(`${PREFIX}/capabilities/query`, params ?? {}),

  // Overview
  getOverview: () =>
    apiClient.get<ApiResponse<Record<string, unknown>>>(`${PREFIX}/overview`),

  // Workflows
  queryWorkflows: (params?: { pagination?: { page: number; page_size: number }; status?: string }) =>
    apiClient.post<PagedResponse<Workflow>>(`${PREFIX}/workflows/query`, params ?? { pagination: { page: 1, page_size: 20 } }),
  getWorkflow: (rid: string) =>
    apiClient.get<ApiResponse<Workflow>>(`${PREFIX}/workflows/${rid}`),
  createWorkflow: (data: Record<string, unknown>) =>
    apiClient.post<ApiResponse<Workflow>>(`${PREFIX}/workflows`, data),
  updateWorkflow: (rid: string, data: Record<string, unknown>) =>
    apiClient.put<ApiResponse<Workflow>>(`${PREFIX}/workflows/${rid}`, data),
  deleteWorkflow: (rid: string) =>
    apiClient.delete<ApiResponse<null>>(`${PREFIX}/workflows/${rid}`),
  executeWorkflow: (rid: string, inputs: Record<string, unknown>) =>
    apiClient.post<ApiResponse<WorkflowExecution>>(`${PREFIX}/workflows/${rid}/execute`, { inputs }),
};
