import { render, screen, fireEvent } from "@testing-library/react";
import { EventDetailModal } from "../EventDetailModal";
import type { EventRecord } from "@/components/ingest/types";

jest.mock("@/components/ingest/ingest-terminal.module.css", () => ({
  exportModalOverlay: "overlay",
  exportModal: "modal",
  exportModalHead: "head",
  exportModalTitle: "title",
  modalIconBtn: "iconBtn",
  exportModalBody: "body",
  fieldLabel: "fieldLabel",
  btn: "btn",
  secondaryBtn: "secondaryBtn",
  exportModalActions: "actions",
}));

jest.mock("@/components/ingest/formatters", () => ({
  formatDateTime: (v: string) => v,
}));

jest.mock("@/components/events/CopyEventLink", () => ({
  CopyEventLink: () => <button>Copy Link</button>,
}));

jest.mock("../JsonHighlight", () => ({
  JsonHighlight: ({ data }: { data: unknown }) => (
    <div data-testid="json-highlight">{JSON.stringify(data)}</div>
  ),
}));

const mockEvent: EventRecord = {
  id: "evt-123",
  contractId: "CAABC",
  contractName: "TestContract",
  eventType: "TRANSFER",
  ledger: 12345,
  eventIndex: 2,
  timestamp: "2024-01-01T00:00:00Z",
  txHash: "TXHASH123",
  payload: { amount: "100", from: "A", to: "B" },
  payloadHash: "PHASH",
  schemaVersion: "1.0",
  validationStatus: "valid",
};

describe("EventDetailModal", () => {
  const onClose = jest.fn();

  beforeEach(() => {
    jest.clearAllMocks();
    Object.assign(navigator, {
      clipboard: {
        writeText: jest.fn().mockResolvedValue(undefined),
      },
    });
  });

  it("renders event details", () => {
    render(<EventDetailModal event={mockEvent} onClose={onClose} />);
    expect(screen.getByText("Event Details")).toBeInTheDocument();
    expect(screen.getByText("evt-123")).toBeInTheDocument();
    expect(screen.getByText("CAABC")).toBeInTheDocument();
    expect(screen.getByText("TestContract")).toBeInTheDocument();
    expect(screen.getByText("TXHASH123")).toBeInTheDocument();
    expect(screen.getByText("TRANSFER")).toBeInTheDocument();
  });

  it("closes when close button clicked", () => {
    render(<EventDetailModal event={mockEvent} onClose={onClose} />);
    fireEvent.click(screen.getByLabelText("Close event details"));
    expect(onClose).toHaveBeenCalled();
  });

  it("closes when overlay clicked", () => {
    render(<EventDetailModal event={mockEvent} onClose={onClose} />);
    const overlay = screen.getByRole("dialog").parentElement!;
    fireEvent.click(overlay);
    expect(onClose).toHaveBeenCalled();
  });

  it("switches payload view to HEX", () => {
    render(<EventDetailModal event={mockEvent} onClose={onClose} />);
    fireEvent.click(screen.getByLabelText("View payload as HEX"));
    expect(screen.getByLabelText("View payload as HEX")).toHaveAttribute("aria-pressed", "true");
  });

  it("copies event id when copy clicked", async () => {
    render(<EventDetailModal event={mockEvent} onClose={onClose} />);
    const copyButtons = screen.getAllByRole("button", { name: /Copy/i });
    fireEvent.click(copyButtons[0]);
    expect(navigator.clipboard.writeText).toHaveBeenCalledWith("evt-123");
  });

  it("renders metadata badges", () => {
    render(<EventDetailModal event={mockEvent} onClose={onClose} />);
    expect(screen.getByText("Ledger")).toBeInTheDocument();
    expect(screen.getByText("12345")).toBeInTheDocument();
    expect(screen.getByText("Payload Hash")).toBeInTheDocument();
  });
});
