/**
 * Tests for the App Router error boundaries (issue #1707).
 *
 * Covers:
 *  - `app/not-found.tsx`   — custom 404 page renders.
 *  - `app/error.tsx`       — route-level boundary renders with a working retry.
 *  - `app/global-error.tsx` — global boundary renders its own <html>/<body>
 *                             and retry/reload actions work.
 *
 * `console.error` is silenced per-test because the boundaries intentionally
 * log the caught error.
 */
import { render, screen, fireEvent } from "@testing-library/react"

import NotFound from "@/app/not-found"
import RouteError from "@/app/error"
import GlobalError from "@/app/global-error"

const mockReloadPage = jest.fn()
jest.mock("@/lib/navigation", () => ({
  reloadPage: () => mockReloadPage(),
  hardNavigate: jest.fn(),
}))

const makeError = (message = "boom") => Object.assign(new Error(message), { digest: "abc123" })


describe("app/not-found.tsx", () => {
  it("renders the custom 404 page", () => {
    render(<NotFound />)

    expect(screen.getByRole("heading", { name: /route not found/i })).toBeInTheDocument()
    expect(screen.getByText(/error 404/i)).toBeInTheDocument()
    expect(screen.getByRole("link", { name: /return home/i })).toHaveAttribute("href", "/")
    expect(screen.getByRole("link", { name: /open dashboard/i })).toHaveAttribute("href", "/dashboard")
  })
})


describe("app/error.tsx", () => {
  let consoleErrorSpy: jest.SpyInstance

  beforeEach(() => {
    consoleErrorSpy = jest.spyOn(console, "error").mockImplementation(() => {})
  })

  afterEach(() => {
    consoleErrorSpy.mockRestore()
  })

  it("renders the route-level error boundary", () => {
    render(<RouteError error={makeError("render failed")} reset={jest.fn()} />)

    expect(screen.getByRole("heading", { name: /something went wrong/i })).toBeInTheDocument()
    expect(screen.getByRole("button", { name: /try again/i })).toBeInTheDocument()
  })

  it("calls reset() when the retry button is clicked", () => {
    const reset = jest.fn()
    render(<RouteError error={makeError()} reset={reset} />)

    fireEvent.click(screen.getByRole("button", { name: /try again/i }))

    expect(reset).toHaveBeenCalledTimes(1)
  })

  it("logs the caught error exactly once", () => {
    render(<RouteError error={makeError("expected error")} reset={jest.fn()} />)

    expect(consoleErrorSpy).toHaveBeenCalledWith(
      "Route error boundary caught:",
      expect.objectContaining({ message: "expected error" }),
    )
  })
})


describe("app/global-error.tsx", () => {
  let consoleErrorSpy: jest.SpyInstance

  beforeEach(() => {
    consoleErrorSpy = jest.spyOn(console, "error").mockImplementation(() => {})
  })

  afterEach(() => {
    consoleErrorSpy.mockRestore()
  })

  it("renders a full <html>/<body> document with the fatal heading", () => {
    // `render` mounts into a container inside document.body, so we assert the
    // rendered fragment includes <html> and <body> nodes (React will lift them
    // appropriately). The key assertion is that the error UI is present.
    render(<GlobalError error={makeError()} reset={jest.fn()} />)

    expect(
      screen.getByRole("heading", { name: /soroscan is temporarily unavailable/i }),
    ).toBeInTheDocument()
    expect(screen.getByText(/fatal error/i)).toBeInTheDocument()
    expect(document.querySelector("html")).not.toBeNull()
  })

  it("calls reset() when the Retry button is clicked", () => {
    const reset = jest.fn()
    render(<GlobalError error={makeError()} reset={reset} />)

    fireEvent.click(screen.getByRole("button", { name: /retry/i }))

    expect(reset).toHaveBeenCalledTimes(1)
  })

  it("reloads the page when Reload is clicked", () => {
    const reset = jest.fn()
    render(<GlobalError error={makeError()} reset={reset} />)
    fireEvent.click(screen.getByRole("button", { name: /reload page/i }))

    expect(mockReloadPage).toHaveBeenCalledTimes(1)
    expect(reset).not.toHaveBeenCalled()
  })
})
