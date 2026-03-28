import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { AssetMappingEditor } from "./asset-mapping-editor";
import type { PropertyType } from "@/types/ontology";

const mockConnections = [
  { rid: "ri.conn.1", display_name: "Production DB", connector_type: "postgresql" },
  { rid: "ri.conn.2", display_name: "Staging DB", connector_type: "mysql" },
];

vi.mock("@tanstack/react-query", () => ({
  useQuery: () => ({
    data: { data: mockConnections },
    isLoading: false,
    error: null,
  }),
}));

vi.mock("@/lib/api/data", () => ({
  dataApi: {
    queryConnections: vi.fn(),
  },
}));

const defaultProps = {
  rid: "ri.obj.1",
  assetMapping: null,
  properties: [] as PropertyType[],
  onSave: vi.fn(),
};

beforeEach(() => {
  vi.clearAllMocks();
});

describe("AssetMappingEditor", () => {
  it("renders empty form when no asset mapping exists", () => {
    render(<AssetMappingEditor {...defaultProps} />);

    expect(screen.getByLabelText("Connection")).toBeInTheDocument();
    expect(screen.getByLabelText("Schema Name")).toBeInTheDocument();
    expect(screen.getByLabelText("Table Name")).toBeInTheDocument();
    expect(
      screen.getByText('No column mappings defined. Click "Add Mapping" to start.'),
    ).toBeInTheDocument();
  });

  it("populates form fields from existing asset mapping", () => {
    const existingMapping = {
      connection_rid: "ri.conn.1",
      schema_name: "public",
      table_name: "employees",
      column_mappings: [
        { property_api_name: "name", column_name: "employee_name" },
      ],
    };

    render(
      <AssetMappingEditor
        {...defaultProps}
        assetMapping={existingMapping}
      />,
    );

    expect(screen.getByLabelText("Schema Name")).toHaveValue("public");
    expect(screen.getByLabelText("Table Name")).toHaveValue("employees");
    expect(screen.getByDisplayValue("name")).toBeInTheDocument();
    expect(screen.getByDisplayValue("employee_name")).toBeInTheDocument();
  });

  it("add mapping row button works", () => {
    render(<AssetMappingEditor {...defaultProps} />);

    const addButton = screen.getByText("Add Mapping");
    fireEvent.click(addButton);

    expect(screen.getByPlaceholderText("property_api_name")).toBeInTheDocument();
    expect(screen.getByPlaceholderText("column_name")).toBeInTheDocument();
  });

  it("remove mapping row button works", () => {
    const existingMapping = {
      connection_rid: "",
      schema_name: "",
      table_name: "",
      column_mappings: [
        { property_api_name: "name", column_name: "col_name" },
      ],
    };

    render(
      <AssetMappingEditor
        {...defaultProps}
        assetMapping={existingMapping}
      />,
    );

    expect(screen.getByDisplayValue("name")).toBeInTheDocument();

    // The remove button is the X icon button in each row
    const removeButtons = screen.getAllByRole("button").filter((btn) => {
      // Find the button that is not "Add Mapping" or "Save Mapping"
      const text = btn.textContent ?? "";
      return !text.includes("Add Mapping") && !text.includes("Save") && !text.includes("Auto");
    });
    expect(removeButtons.length).toBeGreaterThan(0);
    fireEvent.click(removeButtons[0]);

    expect(screen.queryByDisplayValue("name")).not.toBeInTheDocument();
  });

  it("save button calls onSave with correct data", async () => {
    const onSave = vi.fn().mockResolvedValue(undefined);
    const existingMapping = {
      connection_rid: "ri.conn.1",
      schema_name: "public",
      table_name: "users",
      column_mappings: [
        { property_api_name: "email", column_name: "user_email" },
      ],
    };

    render(
      <AssetMappingEditor
        {...defaultProps}
        assetMapping={existingMapping}
        onSave={onSave}
      />,
    );

    const saveButton = screen.getByText("Save Mapping");
    fireEvent.click(saveButton);

    await waitFor(() => {
      expect(onSave).toHaveBeenCalledWith({
        connection_rid: "ri.conn.1",
        schema_name: "public",
        table_name: "users",
        column_mappings: [
          { property_api_name: "email", column_name: "user_email" },
        ],
      });
    });
  });

  it("connection select loads options from API", () => {
    render(<AssetMappingEditor {...defaultProps} />);

    const connectionSelect = screen.getByLabelText("Connection");
    expect(connectionSelect).toBeInTheDocument();

    // Check that options from mock connections are rendered
    expect(screen.getByText("Production DB (postgresql)")).toBeInTheDocument();
    expect(screen.getByText("Staging DB (mysql)")).toBeInTheDocument();
  });
});
