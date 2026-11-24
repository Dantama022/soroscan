import { render, screen } from "@testing-library/react";
import { EventChart } from "../EventChart";
import { MetricsCard } from "../MetricsCard";
import { WebhookStats } from "../WebhookStats";
import { Activity } from "lucide-react";

describe("Admin chart and metric components", () => {
  describe("EventChart", () => {
    it("renders title and data bars", () => {
      const data = [
        { label: "00:00", value: 10 },
        { label: "01:00", value: 20 },
      ];
      render(<EventChart data={data} title="EVENTS" />);
      expect(screen.getByText("[EVENTS]")).toBeInTheDocument();
      expect(screen.getByText("10")).toBeInTheDocument();
      expect(screen.getByText("20")).toBeInTheDocument();
    });

    it("shows loading state", () => {
      render(<EventChart data={[]} title="EVENTS" loading />);
      expect(screen.getByText("LOADING_DATA...")).toBeInTheDocument();
    });

    it("handles empty data gracefully", () => {
      render(<EventChart data={[]} title="EMPTY" />);
      expect(screen.getByText("[EMPTY]")).toBeInTheDocument();
    });
  });

  describe("MetricsCard", () => {
    it("renders title and value", () => {
      render(<MetricsCard title="Total" value={1234} icon={Activity} />);
      expect(screen.getByText("[Total]")).toBeInTheDocument();
      expect(screen.getByText("1234")).toBeInTheDocument();
      expect(screen.getByTestId("metrics-card")).toBeInTheDocument();
    });

    it("renders subValue when provided", () => {
      render(<MetricsCard title="Rate" value="99%" subValue="+5% today" icon={Activity} />);
      expect(screen.getByText("+5% today")).toBeInTheDocument();
    });

    it("shows loading placeholder", () => {
      render(<MetricsCard title="Count" value={100} icon={Activity} loading />);
      expect(screen.getByText("---")).toBeInTheDocument();
    });
  });

  describe("WebhookStats", () => {
    it("renders webhook health stats", () => {
      render(<WebhookStats successRate={98.5} avgTime={125} />);
      expect(screen.getByText("[WEBHOOK_HEALTH]")).toBeInTheDocument();
      expect(screen.getByText("99%")).toBeInTheDocument();
      expect(screen.getByText("125 ms")).toBeInTheDocument();
      expect(screen.getByText("[OPERATIONAL]")).toBeInTheDocument();
    });

    it("shows loading state", () => {
      render(<WebhookStats successRate={0} avgTime={0} loading />);
      expect(screen.getByText("--%")).toBeInTheDocument();
      expect(screen.getByText("--- ms")).toBeInTheDocument();
    });
  });
});
