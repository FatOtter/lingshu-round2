export type CapabilityType = "action" | "global_function" | "workflow";
export type ExecutionStatus = "running" | "completed" | "failed" | "pending_confirmation" | "cancelled";
export type SafetyLevel = "SAFETY_READ_ONLY" | "SAFETY_IDEMPOTENT_WRITE" | "SAFETY_NON_IDEMPOTENT" | "SAFETY_CRITICAL";

export interface CapabilityDescriptor {
  type: CapabilityType;
  rid: string;
  api_name: string;
  display_name: string;
  description: string;
  parameters: Array<{
    name: string;
    type: string;
    required: boolean;
    description: string;
  }>;
  safety_level: SafetyLevel;
}

export interface Execution {
  execution_id: string;
  capability_type: CapabilityType;
  capability_rid: string;
  status: ExecutionStatus;
  params: Record<string, unknown>;
  result: Record<string, unknown> | null;
  safety_level: SafetyLevel;
  started_at: string;
  completed_at: string | null;
}

export interface GlobalFunction {
  rid: string;
  api_name: string;
  display_name: string;
  description: string;
  parameters: Record<string, unknown>;
  implementation: Record<string, unknown>;
  version: number;
  is_active: boolean;
  created_at: string;
  updated_at: string;
}

// Workflow types

export type WorkflowStatus = "draft" | "active" | "archived";

export interface WorkflowNode {
  node_id: string;
  type: "action" | "global_function" | "condition" | "wait";
  capability_rid: string | null;
  input_mappings: Record<string, unknown>;
  position: { x: number; y: number };
  label: string | null;
}

export interface WorkflowEdge {
  source_node_id: string;
  target_node_id: string;
  condition: string | null;
}

export interface Workflow {
  rid: string;
  api_name: string;
  display_name: string;
  description: string | null;
  nodes: WorkflowNode[];
  edges: WorkflowEdge[];
  safety_level: SafetyLevel;
  status: WorkflowStatus;
  version: number;
  is_active: boolean;
  created_at: string;
  updated_at: string;
}

export interface WorkflowExecution {
  execution_id: string;
  workflow_rid: string;
  status: string;
  steps: Array<{
    node_id: string;
    status: string;
    result?: Record<string, unknown>;
    error?: string;
  }>;
  outputs: Record<string, unknown>;
  started_at: string;
  completed_at: string | null;
}
