import { render, screen, fireEvent } from "@testing-library/react";
import "@testing-library/jest-dom";
import { Modal } from "../components/terminal/Modal";

describe("Terminal Modal", () => {
  it("does not render when closed", () => {
    render(
      <Modal isOpen={false} onClose={jest.fn()} title="TEST">
        <p>content</p>
      </Modal>,
    );
    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
  });

  it("renders as an accessible dialog when open", () => {
    render(
      <Modal isOpen={true} onClose={jest.fn()} title="CONFIRM_DELETE">
        <p>content</p>
      </Modal>,
    );
    const dialog = screen.getByRole("dialog");
    expect(dialog).toBeInTheDocument();
    expect(dialog).toHaveAttribute("aria-modal", "true");
    expect(dialog).toHaveAttribute("aria-label", "CONFIRM_DELETE");
  });

  it("calls onClose when Escape is pressed", () => {
    const onClose = jest.fn();
    render(
      <Modal isOpen={true} onClose={onClose} title="CONFIRM_DELETE">
        <p>content</p>
      </Modal>,
    );

    fireEvent.keyDown(document, { key: "Escape" });

    expect(onClose).toHaveBeenCalledTimes(1);
  });

  it("calls onClose when the backdrop overlay is clicked", () => {
    const onClose = jest.fn();
    const { container } = render(
      <Modal isOpen={true} onClose={onClose} title="CONFIRM_DELETE">
        <p>content</p>
      </Modal>,
    );

    const overlay = container.querySelector(".backdrop-blur-sm");
    expect(overlay).not.toBeNull();
    fireEvent.click(overlay as Element);

    expect(onClose).toHaveBeenCalledTimes(1);
  });

  it("traps Tab focus within the modal", () => {
    render(
      <Modal isOpen={true} onClose={jest.fn()} title="REGISTER_CONTRACT">
        <button>First</button>
        <button>Last</button>
      </Modal>,
    );

    const buttons = screen.getAllByRole("button");
    const last = buttons[buttons.length - 1];

    last.focus();
    expect(document.activeElement).toBe(last);

    fireEvent.keyDown(document, { key: "Tab" });

    expect(document.activeElement).not.toBe(last);
  });

  it("restores focus to the previously focused element on close", () => {
    const trigger = document.createElement("button");
    trigger.textContent = "Open";
    document.body.appendChild(trigger);
    trigger.focus();
    expect(document.activeElement).toBe(trigger);

    const { rerender } = render(
      <Modal isOpen={true} onClose={jest.fn()} title="CONFIRM_DELETE">
        <p>content</p>
      </Modal>,
    );

    expect(document.activeElement).not.toBe(trigger);

    rerender(
      <Modal isOpen={false} onClose={jest.fn()} title="CONFIRM_DELETE">
        <p>content</p>
      </Modal>,
    );

    expect(document.activeElement).toBe(trigger);
    document.body.removeChild(trigger);
  });
});
