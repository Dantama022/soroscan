import React from "react"
import { render, screen, fireEvent } from "@testing-library/react"
import { Alert } from "../components/ui/alert"

describe("Alert Component", () => {
  it("renders the title and description correctly", () => {
    render(<Alert title="System Update" description="Your profile has been updated." />)
    expect(screen.getByText("System Update")).toBeInTheDocument()
    expect(screen.getByText("Your profile has been updated.")).toBeInTheDocument()
  })

  it("renders all variants without crashing", () => {
    const variants = ["info", "success", "warning", "error"] as const
    variants.forEach((variant) => {
      render(<Alert variant={variant} title={`${variant} alert`} />)
      expect(screen.getByText(`${variant} alert`)).toBeInTheDocument()
    })
  })

  it("removes itself from the DOM when dismissed", () => {
    render(<Alert title="Dismiss me" dismissible />)
    
    const alertElement = screen.getByRole("alert")
    expect(alertElement).toBeInTheDocument()
    
    const closeButton = screen.getByLabelText("Dismiss alert")
    fireEvent.click(closeButton)
    
    expect(screen.queryByRole("alert")).not.toBeInTheDocument()
  })

  it("does not render dismiss button if dismissible prop is false and onDismiss is omitted", () => {
    render(<Alert title="Static Alert" />)
    expect(screen.queryByLabelText("Dismiss alert")).not.toBeInTheDocument()
  })
})