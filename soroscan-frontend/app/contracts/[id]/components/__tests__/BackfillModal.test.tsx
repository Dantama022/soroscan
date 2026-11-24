import type { ComponentProps, ReactNode } from "react";
import { render, screen, fireEvent } from "@testing-library/react";
import { BackfillModal } from "../BackfillModal";

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

jest.mock("@/components/terminal/Button", () => ({
  Button: ({ children, onClick, ...props }: ComponentProps<"button">) => (
    <button onClick={onClick} {...props}>
      {children}
    </button>
  ),
}));

describe("BackfillModal", () => {
  const onClose = jest.fn();

  beforeEach(() => {
    jest.clearAllMocks();
  });

  it("renders when open with no task", () => {
    render(<BackfillModal isOpen onClose={onClose} task={null} />);
    expect(screen.getByRole("dialog")).toBeInTheDocument();
    expect(screen.getByText(/No task information/)).toBeInTheDocument();
  });

  it("displays task details", () => {
    const task = {
      taskId: "task-123",
      contractId: "CA123",
      status: "running" as const,
      progress: 45,
      message: "Processing...",
    };
    render(<BackfillModal isOpen onClose={onClose} task={task} />);
    expect(screen.getByText("task-123")).toBeInTheDocument();
    expect(screen.getByText("RUNNING")).toBeInTheDocument();
    expect(screen.getByText("45%")).toBeInTheDocument();
    expect(screen.getByText("Processing...")).toBeInTheDocument();
  });

  it("displays completed status", () => {
    const task = {
      taskId: "task-456",
      contractId: "CA123",
      status: "completed" as const,
    };
    render(<BackfillModal isOpen onClose={onClose} task={task} />);
    expect(screen.getByText("COMPLETED")).toBeInTheDocument();
  });

  it("displays failed status", () => {
    const task = {
      taskId: "task-789",
      contractId: "CA123",
      status: "failed" as const,
    };
    render(<BackfillModal isOpen onClose={onClose} task={task} />);
    expect(screen.getByText("FAILED")).toBeInTheDocument();
  });

  it("closes when close button clicked", () => {
    const task = {
      taskId: "task-123",
      contractId: "CA123",
      status: "pending" as const,
    };
    render(<BackfillModal isOpen onClose={onClose} task={task} />);
    const closeBtns = screen.getAllByText("Close");
    fireEvent.click(closeBtns[0]);
    expect(onClose).toHaveBeenCalled();
  });
});
