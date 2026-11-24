import type { ComponentProps, ReactNode } from "react";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { DeleteConfirmModal } from "../DeleteConfirmModal";
import { RegisterModal } from "../RegisterModal";

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

jest.mock("@/components/terminal/Input", () => ({
  Input: ({ label, ...props }: ComponentProps<"input"> & { label?: string }) => (
    <label>
      {label}
      <input {...props} />
    </label>
  ),
}));

jest.mock("@/components/terminal/Button", () => ({
  Button: ({ children, type = "button", ...props }: ComponentProps<"button">) => (
    <button type={type} {...props}>
      {children}
    </button>
  ),
}));

describe("Contract modals", () => {
  describe("DeleteConfirmModal", () => {
    const onConfirm = jest.fn();
    const onCancel = jest.fn();

    beforeEach(() => {
      jest.clearAllMocks();
    });

    it("renders when open with contract name", () => {
      render(
        <DeleteConfirmModal isOpen onConfirm={onConfirm} onCancel={onCancel} contractName="MyContract" />
      );
      expect(screen.getByRole("dialog")).toBeInTheDocument();
      expect(screen.getByText(/MyContract/)).toBeInTheDocument();
    });

    it("calls onConfirm when delete clicked", () => {
      render(
        <DeleteConfirmModal isOpen onConfirm={onConfirm} onCancel={onCancel} contractName="MyContract" />
      );
      fireEvent.click(screen.getByTestId("confirm-delete-btn"));
      expect(onConfirm).toHaveBeenCalled();
    });

    it("calls onCancel when cancel clicked", () => {
      render(
        <DeleteConfirmModal isOpen onConfirm={onConfirm} onCancel={onCancel} contractName="MyContract" />
      );
      fireEvent.click(screen.getByText("CANCEL"));
      expect(onCancel).toHaveBeenCalled();
    });

    it("disables buttons when deleting", () => {
      render(
        <DeleteConfirmModal
          isOpen
          onConfirm={onConfirm}
          onCancel={onCancel}
          contractName="MyContract"
          isDeleting
        />
      );
      expect(screen.getByTestId("confirm-delete-btn")).toBeDisabled();
      expect(screen.getByText("CANCEL")).toBeDisabled();
    });
  });

  describe("RegisterModal", () => {
    const onClose = jest.fn();
    const onSubmit = jest.fn().mockResolvedValue(undefined);

    beforeEach(() => {
      jest.clearAllMocks();
    });

    it("renders form when open", () => {
      render(<RegisterModal isOpen onClose={onClose} onSubmit={onSubmit} />);
      expect(screen.getByRole("dialog")).toBeInTheDocument();
      expect(screen.getByTestId("contract-id-input")).toBeInTheDocument();
      expect(screen.getByTestId("contract-name-input")).toBeInTheDocument();
    });

    it("shows validation errors when submitting empty form", async () => {
      render(<RegisterModal isOpen onClose={onClose} onSubmit={onSubmit} />);
      // Submit the form directly: jsdom blocks click-submits on `required` fields.
      fireEvent.submit(screen.getByTestId("register-submit-btn").closest("form")!);
      expect(await screen.findByText(/Contract ID is required/)).toBeInTheDocument();
    });

    it("submits valid form data", async () => {
      render(<RegisterModal isOpen onClose={onClose} onSubmit={onSubmit} />);
      fireEvent.change(screen.getByTestId("contract-id-input"), { target: { value: "CA123" } });
      fireEvent.change(screen.getByTestId("contract-name-input"), { target: { value: "Test" } });
      fireEvent.click(screen.getByTestId("register-submit-btn"));
      await waitFor(() => expect(onSubmit).toHaveBeenCalled());
      expect(onSubmit).toHaveBeenCalledWith(
        expect.objectContaining({
          contractId: "CA123",
          name: "Test",
          status: "active",
        })
      );
      expect(onClose).toHaveBeenCalled();
    });

    it("calls onClose when cancel clicked", () => {
      render(<RegisterModal isOpen onClose={onClose} onSubmit={onSubmit} />);
      fireEvent.click(screen.getByText("CANCEL"));
      expect(onClose).toHaveBeenCalled();
    });

    it("shows error on submit failure", async () => {
      onSubmit.mockRejectedValueOnce(new Error("Failed"));
      render(<RegisterModal isOpen onClose={onClose} onSubmit={onSubmit} />);
      fireEvent.change(screen.getByTestId("contract-id-input"), { target: { value: "CA123" } });
      fireEvent.change(screen.getByTestId("contract-name-input"), { target: { value: "Test" } });
      fireEvent.click(screen.getByTestId("register-submit-btn"));
      expect(await screen.findByText("Failed")).toBeInTheDocument();
    });
  });
});
