import type { ApiResponse, PagedResponse } from "./client";
import { apiClient } from "./client";
import type { Session, Model, Skill, McpConnection, SubAgent } from "@/types/copilot";

const PREFIX = "/copilot/v1";

export const copilotApi = {
  // Sessions
  createSession: (mode: "shell" | "agent", context?: Record<string, unknown>) =>
    apiClient.post<ApiResponse<Session>>(`${PREFIX}/sessions`, { mode, context }),
  getSession: (sessionId: string) =>
    apiClient.get<ApiResponse<Session>>(`${PREFIX}/sessions/${sessionId}`),
  querySessions: (params?: { pagination?: { page: number; page_size: number } }) =>
    apiClient.post<PagedResponse<Session>>(`${PREFIX}/sessions/query`, params ?? { pagination: { page: 1, page_size: 20 } }),
  updateContext: (sessionId: string, context: Record<string, unknown>) =>
    apiClient.put<ApiResponse<Session>>(`${PREFIX}/sessions/${sessionId}/context`, { context }),
  deleteSession: (sessionId: string) =>
    apiClient.delete<ApiResponse<null>>(`${PREFIX}/sessions/${sessionId}`),

  // Messages (SSE handled separately via sse.ts)
  resume: (sessionId: string, approved: boolean) =>
    apiClient.post<ApiResponse<null>>(`${PREFIX}/sessions/${sessionId}/resume`, { approved }),

  // Models
  queryModels: (params?: { pagination?: { page: number; page_size: number } }) =>
    apiClient.post<PagedResponse<Model>>(`${PREFIX}/models/query`, params ?? { pagination: { page: 1, page_size: 20 } }),
  getModel: (rid: string) =>
    apiClient.get<ApiResponse<Model>>(`${PREFIX}/models/${rid}`),
  registerModel: (data: Record<string, unknown>) =>
    apiClient.post<ApiResponse<Model>>(`${PREFIX}/models`, data),
  updateModel: (rid: string, data: Record<string, unknown>) =>
    apiClient.put<ApiResponse<Model>>(`${PREFIX}/models/${rid}`, data),
  deleteModel: (rid: string) =>
    apiClient.delete<ApiResponse<null>>(`${PREFIX}/models/${rid}`),

  // Skills
  querySkills: (params?: { pagination?: { page: number; page_size: number } }) =>
    apiClient.post<PagedResponse<Skill>>(`${PREFIX}/skills/query`, params ?? { pagination: { page: 1, page_size: 20 } }),
  getSkill: (rid: string) =>
    apiClient.get<ApiResponse<Skill>>(`${PREFIX}/skills/${rid}`),
  registerSkill: (data: Record<string, unknown>) =>
    apiClient.post<ApiResponse<Skill>>(`${PREFIX}/skills`, data),
  updateSkill: (rid: string, data: Record<string, unknown>) =>
    apiClient.put<ApiResponse<Skill>>(`${PREFIX}/skills/${rid}`, data),
  deleteSkill: (rid: string) =>
    apiClient.delete<ApiResponse<null>>(`${PREFIX}/skills/${rid}`),

  // MCP
  queryMcp: (params?: { pagination?: { page: number; page_size: number } }) =>
    apiClient.post<PagedResponse<McpConnection>>(`${PREFIX}/mcp/query`, params ?? { pagination: { page: 1, page_size: 20 } }),
  getMcp: (rid: string) =>
    apiClient.get<ApiResponse<McpConnection>>(`${PREFIX}/mcp/${rid}`),
  connectMcp: (data: Record<string, unknown>) =>
    apiClient.post<ApiResponse<McpConnection>>(`${PREFIX}/mcp`, data),
  updateMcp: (rid: string, data: Record<string, unknown>) =>
    apiClient.put<ApiResponse<McpConnection>>(`${PREFIX}/mcp/${rid}`, data),
  deleteMcp: (rid: string) =>
    apiClient.delete<ApiResponse<null>>(`${PREFIX}/mcp/${rid}`),
  discoverTools: (rid: string) =>
    apiClient.post<ApiResponse<Record<string, unknown>[]>>(`${PREFIX}/mcp/${rid}/discover-tools`),
  testConnection: (rid: string) =>
    apiClient.post<ApiResponse<Record<string, unknown>>>(`${PREFIX}/mcp/${rid}/test`),

  // Sub-Agents
  querySubAgents: (params?: { pagination?: { page: number; page_size: number } }) =>
    apiClient.post<PagedResponse<SubAgent>>(`${PREFIX}/sub-agents/query`, params ?? { pagination: { page: 1, page_size: 20 } }),
  getSubAgent: (rid: string) =>
    apiClient.get<ApiResponse<SubAgent>>(`${PREFIX}/sub-agents/${rid}`),
  createSubAgent: (data: Record<string, unknown>) =>
    apiClient.post<ApiResponse<SubAgent>>(`${PREFIX}/sub-agents`, data),
  updateSubAgent: (rid: string, data: Record<string, unknown>) =>
    apiClient.put<ApiResponse<SubAgent>>(`${PREFIX}/sub-agents/${rid}`, data),
  deleteSubAgent: (rid: string) =>
    apiClient.delete<ApiResponse<null>>(`${PREFIX}/sub-agents/${rid}`),

  // Overview
  getOverview: () =>
    apiClient.get<ApiResponse<Record<string, unknown>>>(`${PREFIX}/overview`),
};
