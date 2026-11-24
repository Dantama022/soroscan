import type { ReactNode } from "react";
import { render, screen, fireEvent } from "@testing-library/react";
import { FilterBuilderModal } from "../FilterBuilderModal";

jest.mock("@/components/terminal/Modal", () => ({
  Modal: ({
    isOpen,
    onClose,
    title,
    children,
  }: {
    isOpen: boolean;
    onClose: () => void;
    title?: string;
    children: ReactNode;
  }) =>
    isOpen ? (
      <div role="dialog" aria-label={title}>
        <button onClick={onClose}>Close</button>
        {children}
      </div>
    ) : null,
}));

jest.mock("@/components/ui/WebhookFilterExpressionBuilder", () => ({
  WebhookFilterExpressionBuilder: ({ onChange }: { onChange: (value: unknown) => void }) => (
    <div data-testid="webhook-filter-builder">
      <button onClick={() => onChange({ root: { id: "g1", kind: "group", logic: "OR", children: [] } })}>
        Change
      </button>
    </div>
  ),
  emptyExpression: () => ({ root: { id: "g1", kind: "group", logic: "AND", children: [] } }),
  serializeExpression: () => "event_type = \"TEST\"",
}));

jest.mock("@/components/ui/FilterExpressionTester", () => ({
  FilterExpressionTester: () => <div data-testid="filter-tester" />,
}));

describe("FilterBuilderModal", () => {
  const onClose = jest.fn();
  const onSave = jest.fn();

  beforeEach(() => {
    jest.clearAllMocks();
  });

  it("does not render when closed", () => {
    render(<FilterBuilderModal isOpen={false} onClose={onClose} onSave={onSave} />);
    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
  });

  it("renders with build tab active by default", () => {
    render(<FilterBuilderModal isOpen={true} onClose={onClose} onSave={onSave} />);
    expect(screen.getByRole("dialog")).toBeInTheDocument();
    expect(screen.getByTestId("tab-build")).toHaveAttribute("aria-selected", "true");
    expect(screen.getByTestId("webhook-filter-builder")).toBeInTheDocument();
  });

  it("switches to test tab", () => {
    render(<FilterBuilderModal isOpen={true} onClose={onClose} onSave={onSave} />);
    fireEvent.click(screen.getByTestId("tab-test"));
    expect(screen.getByTestId("tab-test")).toHaveAttribute("aria-selected", "true");
    expect(screen.getByTestId("filter-tester")).toBeInTheDocument();
  });

  it("calls onSave with serialized expression and closes", () => {
    render(<FilterBuilderModal isOpen={true} onClose={onClose} onSave={onSave} />);
    fireEvent.click(screen.getByTestId("save-filter-btn"));
    expect(onSave).toHaveBeenCalledWith("event_type = \"TEST\"", expect.any(Object));
    expect(onClose).toHaveBeenCalled();
  });

  it("calls onClose when cancel is clicked", () => {
    render(<FilterBuilderModal isOpen={true} onClose={onClose} onSave={onSave} />);
    fireEvent.click(screen.getByTestId("cancel-filter-btn"));
    expect(onClose).toHaveBeenCalled();
  });

  it("resets expression when reopened", () => {
    const { rerender } = render(
      <FilterBuilderModal
        isOpen={true}
        onClose={onClose}
        onSave={onSave}
        initialExpression={{ root: { id: "x", kind: "group", logic: "OR", children: [] } }}
      />
    );
    rerender(<FilterBuilderModal isOpen={false} onClose={onClose} onSave={onSave} />);
    rerender(<FilterBuilderModal isOpen={true} onClose={onClose} onSave={onSave} />);
    expect(screen.getByTestId("tab-build")).toHaveAttribute("aria-selected", "true");
  });
});
