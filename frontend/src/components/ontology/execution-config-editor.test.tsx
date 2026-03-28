import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { ExecutionConfigEditor } from "./execution-config-editor";

const defaultProps = {
  initialValue: { engine: "python", timeout: 30 },
  onSave: vi.fn(),
};

beforeEach(() => {
  vi.clearAllMocks();
});

describe("ExecutionConfigEditor", () => {
  it("renders JSON content in textarea", () => {
    render(<ExecutionConfigEditor {...defaultProps} />);

    const textarea = screen.getByRole("textbox");
    expect(textarea).toBeInTheDocument();

    const expected = JSON.stringify({ engine: "python", timeout: 30 }, null, 2);
    expect(textarea).toHaveValue(expected);
  });

  it("shows error for invalid JSON", () => {
    render(<ExecutionConfigEditor {...defaultProps} />);

    const textarea = screen.getByRole("textbox");
    fireEvent.change(textarea, { target: { value: "{ invalid json" } });

    expect(screen.getByText(/JSON Error:/)).toBeInTheDocument();
  });

  it("format button pretty-prints JSON", () => {
    render(<ExecutionConfigEditor {...defaultProps} />);

    const textarea = screen.getByRole("textbox");
    // Set compact JSON
    fireEvent.change(textarea, {
      target: { value: '{"engine":"python","timeout":30}' },
    });

    const formatButton = screen.getByText("Format JSON");
    fireEvent.click(formatButton);

    const expected = JSON.stringify({ engine: "python", timeout: 30 }, null, 2);
    expect(textarea).toHaveValue(expected);
  });

  it("save button calls onSave with parsed JSON", async () => {
    const onSave = vi.fn().mockResolvedValue(undefined);

    render(
      <ExecutionConfigEditor
        initialValue={{ engine: "python", timeout: 30 }}
        onSave={onSave}
      />,
    );

    const saveButton = screen.getByText("Save Config");
    fireEvent.click(saveButton);

    await waitFor(() => {
      expect(onSave).toHaveBeenCalledWith({ engine: "python", timeout: 30 });
    });
  });
});
