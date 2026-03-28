export interface Filter {
  field: string;
  operator: "eq" | "neq" | "gt" | "gte" | "lt" | "lte" | "in" | "not_in" | "like" | "is_null" | "is_not_null";
  value: unknown;
}

export interface SortSpec {
  field: string;
  direction: "asc" | "desc";
}

export interface Pagination {
  total: number;
  page: number;
  page_size: number;
  has_next: boolean;
}
