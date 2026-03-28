export interface Connection {
  rid: string;
  api_name: string;
  display_name: string;
  connector_type: string;
  config: Record<string, unknown>;
  status: "active" | "inactive" | "error";
  created_at: string;
  updated_at: string;
}

export interface Instance {
  primary_key: string;
  fields: Record<string, unknown>;
}

export interface QueryResult {
  instances: Instance[];
  columns: Array<{
    api_name: string;
    display_name: string;
    data_type: string;
    is_masked: boolean;
    sortable: boolean;
    filterable: boolean;
  }>;
  total: number;
}

export interface SchemaMetadata {
  object_type_rid: string;
  columns: Array<{
    api_name: string;
    display_name: string;
    data_type: string;
  }>;
}
