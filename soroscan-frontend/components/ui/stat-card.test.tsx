import * as React from "react"
import { render, screen } from "@testing-library/react"
import { Activity } from "lucide-react"

import { StatCard } from "./stat-card"

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

/** Render a StatCard and return the top-level container element. */
function renderCard(props: React.ComponentPropsWithoutRef<typeof StatCard>) {
  const { container } = render(<StatCard {...props} />)
  return container.firstElementChild as HTMLElement
}

// ---------------------------------------------------------------------------
// Basic rendering
// ---------------------------------------------------------------------------

describe("StatCard — basic rendering", () => {
  it("renders the title", () => {
    render(<StatCard title="Total Events" value={1234} />)
    expect(screen.getByText("Total Events")).toBeInTheDocument()
  })

  it("renders a numeric value", () => {
    render(<StatCard title="Ledgers" value={99_000} />)
    expect(screen.getByText("99000")).toBeInTheDocument()
  })

  it("renders a string value", () => {
    render(<StatCard title="Status" value="Healthy" />)
    expect(screen.getByText("Healthy")).toBeInTheDocument()
  })

  it("renders both title and value together", () => {
    render(<StatCard title="Contracts" value="42" />)
    expect(screen.getByText("Contracts")).toBeInTheDocument()
    expect(screen.getByText("42")).toBeInTheDocument()
  })

  it("applies a custom className to the outer card", () => {
    const el = renderCard({ title: "T", value: "V", className: "my-custom-class" })
    expect(el).toHaveClass("my-custom-class")
  })
})

// ---------------------------------------------------------------------------
// Trend indicator
// ---------------------------------------------------------------------------

describe("StatCard — trendValue", () => {
  it("does not render a trend section when trendValue is omitted", () => {
    render(<StatCard title="Events" value={100} />)
    expect(screen.queryByText(/vs last month/i)).not.toBeInTheDocument()
  })

  it("renders the absolute percentage and 'vs last month' label when trendValue is provided", () => {
    render(<StatCard title="Events" value={100} trendValue={12} />)
    expect(screen.getByText("12%")).toBeInTheDocument()
    expect(screen.getByText(/vs last month/i)).toBeInTheDocument()
  })

  it("shows the absolute value for a negative trend (no minus sign in text)", () => {
    render(<StatCard title="Events" value={100} trendValue={-8} />)
    // Math.abs(-8) = 8 — the component renders the absolute value
    expect(screen.getByText("8%")).toBeInTheDocument()
  })

  it("applies green text classes for a positive trend", () => {
    render(<StatCard title="Events" value={100} trendValue={5} />)
    const pct = screen.getByText("5%")
    // Matches both light and dark variants the component applies
    expect(pct.className).toMatch(/text-green/)
  })

  it("applies red text classes for a negative trend", () => {
    render(<StatCard title="Events" value={100} trendValue={-5} />)
    const pct = screen.getByText("5%")
    expect(pct.className).toMatch(/text-red/)
  })

  it("applies neutral (slate) text classes for a zero trend", () => {
    render(<StatCard title="Events" value={100} trendValue={0} />)
    const pct = screen.getByText("0%")
    expect(pct.className).toMatch(/text-slate/)
  })
})

// ---------------------------------------------------------------------------
// Icon slot
// ---------------------------------------------------------------------------

describe("StatCard — icon", () => {
  it("does not render an icon wrapper when icon is omitted", () => {
    const { container } = render(<StatCard title="Events" value={100} />)
    // The icon is wrapped in a rounded-full div
    expect(container.querySelector(".rounded-full")).not.toBeInTheDocument()
  })

  it("renders the icon inside a rounded container when provided", () => {
    const { container } = render(
      <StatCard title="Events" value={100} icon={<Activity data-testid="stat-icon" />} />
    )
    expect(screen.getByTestId("stat-icon")).toBeInTheDocument()
    expect(container.querySelector(".rounded-full")).toBeInTheDocument()
  })
})

// ---------------------------------------------------------------------------
// Loading skeleton
// ---------------------------------------------------------------------------

describe("StatCard — isLoading", () => {
  it("renders the animate-pulse skeleton instead of title/value when isLoading=true", () => {
    const { container } = render(
      <StatCard title="Events" value={100} isLoading />
    )
    expect(container.querySelector(".animate-pulse")).toBeInTheDocument()
    // Title and value must not be visible during loading
    expect(screen.queryByText("Events")).not.toBeInTheDocument()
    expect(screen.queryByText("100")).not.toBeInTheDocument()
  })

  it("renders the skeleton icon placeholder circle", () => {
    const { container } = render(
      <StatCard title="Events" value={100} isLoading />
    )
    // The skeleton has a circle placeholder: h-10 w-10 rounded-full
    const circle = container.querySelector(".rounded-full")
    expect(circle).toBeInTheDocument()
  })

  it("does not render the skeleton when isLoading is false", () => {
    const { container } = render(
      <StatCard title="Events" value={100} isLoading={false} />
    )
    expect(container.querySelector(".animate-pulse")).not.toBeInTheDocument()
    expect(screen.getByText("Events")).toBeInTheDocument()
  })

  it("does not render the skeleton when isLoading is omitted", () => {
    const { container } = render(<StatCard title="Events" value={100} />)
    expect(container.querySelector(".animate-pulse")).not.toBeInTheDocument()
  })
})
