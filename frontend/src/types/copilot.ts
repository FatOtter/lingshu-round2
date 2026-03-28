export interface Session {
  session_id: string;
  mode: "shell" | "agent";
  title: string | null;
  context: SessionContext;
  model_rid: string | null;
  status: "active" | "archived";
  created_at: string;
  last_active_at: string;
}

export interface SessionContext {
  module?: string;
  page?: string;
  entity_rid?: string;
  branch?: string;
}

export interface Model {
  rid: string;
  api_name: string;
  display_name: string;
  provider: string;
  connection: Record<string, unknown>;
  parameters: Record<string, unknown>;
  is_default: boolean;
  created_at: string;
  updated_at: string;
}

export interface Skill {
  rid: string;
  api_name: string;
  display_name: string;
  description: string | null;
  system_prompt: string;
  tool_bindings: Record<string, unknown>[];
  enabled: boolean;
  created_at: string;
  updated_at: string;
}

export interface McpConnection {
  rid: string;
  api_name: string;
  display_name: string;
  description: string | null;
  transport: Record<string, unknown>;
  auth: Record<string, unknown> | null;
  discovered_tools: Record<string, unknown>[];
  status: string;
  enabled: boolean;
  created_at: string;
  updated_at: string;
}

export interface SubAgent {
  rid: string;
  api_name: string;
  display_name: string;
  description: string | null;
  model_rid: string | null;
  system_prompt: string | null;
  tool_bindings: Record<string, unknown>[];
  safety_policy: Record<string, unknown>;
  enabled: boolean;
  created_at: string;
  updated_at: string;
}

export interface Message {
  role: "user" | "assistant";
  content: string;
  timestamp: string;
  events?: A2UIEvent[];
}

export interface A2UIEvent {
  type: string;
  data: Record<string, unknown>;
  event_id?: number;
}
