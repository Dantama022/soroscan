"use client"

import { useEffect } from "react"
import { Button } from "@/components/terminal/Button"

/**
 * Route-level error boundary (issue #1707).
 *
 * Next.js renders this component whenever a Server Component or Client
 * Component below this segment throws during render. It replaces only the
 * failing segment, so the root layout (fonts, providers, global styles) is
 * preserved — which is why we can use Tailwind / `Button` freely here.
 *
 * The `reset` callback re-renders the failed segment without a full page
 * reload, allowing transient errors (e.g. flaky network fetches) to recover.
 */
export default function Error({
  error,
  reset,
}: {
  error: Error & { digest?: string }
  reset: () => void
}) {
  useEffect(() => {
    // Surface the error to the browser console for debugging. Production
    // deployments should additionally forward this to their error tracker.
    console.error("Route error boundary caught:", error)
  }, [error])

  return (
    <div className="min-h-[60vh] flex items-center justify-center px-4 py-16">
      <div className="w-full max-w-2xl border-terminal border-terminal-danger/40 bg-terminal-black p-8 sm:p-12">
        <p className="font-terminal-mono text-terminal-danger/70 text-sm tracking-widest mb-4">
          RUNTIME ERROR
        </p>

        <h1 className="font-terminal-mono text-terminal-danger text-2xl sm:text-4xl font-bold mb-6">
          Something went wrong
        </h1>

        <p className="font-terminal-mono text-terminal-green/80 text-sm sm:text-base mb-2">
          <span className="text-terminal-cyan">$</span> soroscan run{" "}
          <span className="text-terminal-danger">--recover</span>
        </p>
        <p className="font-terminal-mono text-terminal-green/60 text-xs sm:text-sm mb-8">
          This route failed to render. You can retry without losing the rest of
          the app.
        </p>

        {process.env.NODE_ENV !== "production" && (
          <pre className="font-terminal-mono text-xs text-terminal-danger/70 bg-terminal-black border border-terminal-danger/20 p-4 mb-6 overflow-x-auto whitespace-pre-wrap">
            {error.message}
            {error.digest ? `\n\ndigest: ${error.digest}` : ""}
          </pre>
        )}

        <div className="flex flex-wrap gap-3">
          <Button variant="primary" size="default" onClick={() => reset()}>
            Try again
          </Button>
          <Button
            variant="secondary"
            size="default"
            onClick={() => {
              if (typeof window !== "undefined") {
                window.location.href = "/"
              }
            }}
          >
            Go home
          </Button>
        </div>
      </div>
    </div>
  )
}