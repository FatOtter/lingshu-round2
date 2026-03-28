export type VersionStatus = "ACTIVE" | "DRAFT" | "STAGING" | "DELETED";
export type DataType = "STRING" | "INTEGER" | "FLOAT" | "BOOLEAN" | "DATE" | "DATETIME" | "TIMESTAMP" | "ENUM" | "JSON" | "ARRAY" | "REFERENCE";

export interface PropertyType {
  rid: string;
  api_name: string;
  display_name: string;
  description: string | null;
  data_type: string;
  inherit_from_shared_property_type_rid: string | null;
  physical_column: string | null;
  virtual_expression: string | null;
  widget: Record<string, unknown> | null;
  validation: Record<string, unknown> | null;
  compliance: Record<string, unknown> | null;
}

export interface ObjectType {
  rid: string;
  api_name: string;
  display_name: string;
  description: string;
  property_types: PropertyType[];
  implements_interface_type_rids: string[];
  primary_key_property_type_rids: string[];
  validation: Record<string, unknown> | null;
  asset_mapping: Record<string, unknown> | null;
  lifecycle_status: string;
  version_status: VersionStatus;
  is_active: boolean;
  created_at: string;
  updated_at: string;
}

export interface LinkType {
  rid: string;
  api_name: string;
  display_name: string;
  description: string;
  source_object_type_rid: string | null;
  source_interface_type_rid: string | null;
  target_object_type_rid: string | null;
  target_interface_type_rid: string | null;
  cardinality: "ONE_TO_ONE" | "ONE_TO_MANY" | "MANY_TO_ONE" | "MANY_TO_MANY";
  implements_interface_type_rids: string[];
  primary_key_property_type_rids: string[];
  property_types: PropertyType[];
  validation: Record<string, unknown> | null;
  asset_mapping: Record<string, unknown> | null;
  lifecycle_status: string;
  version_status: VersionStatus;
  is_active: boolean;
  created_at: string;
  updated_at: string;
}

export interface InterfaceType {
  rid: string;
  api_name: string;
  display_name: string;
  description: string;
  category: "OBJECT_INTERFACE" | "LINK_INTERFACE";
  extends_interface_type_rids: string[];
  required_shared_property_type_rids: string[];
  link_requirements: Record<string, unknown>[];
  object_constraint: Record<string, unknown> | null;
  lifecycle_status: string;
  version_status: VersionStatus;
  is_active: boolean;
  created_at: string;
  updated_at: string;
}

export interface ActionType {
  rid: string;
  api_name: string;
  display_name: string;
  description: string;
  operates_on_rid: string;
  parameters: Record<string, unknown>[];
  execution: Record<string, unknown>;
  safety_level: string;
  side_effects: Record<string, unknown>[];
  version_status: VersionStatus;
  created_at: string;
  updated_at: string;
}

export interface SharedPropertyType {
  rid: string;
  api_name: string;
  display_name: string;
  description: string;
  data_type: DataType;
  version_status: VersionStatus;
  created_at: string;
  updated_at: string;
}

export interface TopologyNode {
  rid: string;
  type: string;
  api_name: string;
  display_name: string;
}

export interface TopologyEdge {
  source: string;
  target: string;
  label: string;
}

export interface TopologyData {
  nodes: TopologyNode[];
  edges: TopologyEdge[];
}

export interface StagingSummary {
  changes?: Array<{
    entity_type: string;
    rid: string;
    api_name: string;
    change_type: "created" | "updated" | "deleted";
  }>;
  counts?: Record<string, number>;
  total: number;
}

export interface Snapshot {
  snapshot_id: string;
  description: string;
  created_by: string;
  created_at: string;
  entity_count: number;
}
