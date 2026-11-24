"use client"

import { useEffect } from "react"
import { Button } from "@/components/terminal/Button"
import { reloadPage } from "@/lib/navigation"

/**
 * Global error boundary (issue #1707).
 *
 * Rendered when an error is thrown in the root `layout.tsx` itself, or in the
 * root `page.tsx` when no other boundary catches it. Because it *replaces* the
 * root layout, we must render our own `<html>` and `<body>` and cannot rely on
 * providers or context — only on server-independent primitives.
 *
 * The `reset` callback attempts to re-render the root; if the error was caused
 * by a transient issue (network, cache) this can recover. If not, "Reload"
 * forces a full page load.
 */
export default function GlobalError({
  error,
  reset,
}: {
  error: Error & { digest?: string }
  reset: () => void
}) {
  useEffect(() => {
    console.error("Global error boundary caught:", error)
  }, [error])

  return (
    <html lang="en" className="dark">
      <body className="font-terminal-mono antialiased bg-terminal-black text-terminal-green">
        <div className="min-h-screen flex items-center justify-center px-4 py-16">
          <div className="w-full max-w-2xl border-terminal border-terminal-danger/40 bg-terminal-black p-8 sm:p-12">
            <p className="font-terminal-mono text-terminal-danger/70 text-sm tracking-widest mb-4">
              FATAL ERROR
            </p>

            <h1 className="font-terminal-mono text-terminal-danger text-2xl sm:text-4xl font-bold mb-6">
              SoroScan is temporarily unavailable
            </h1>

            <p className="font-terminal-mono text-terminal-green/80 text-sm sm:text-base mb-2">
              <span className="text-terminal-cyan">$</span> soroscan status{" "}
              <span className="text-terminal-danger">--fatal</span>
            </p>
            <p className="font-terminal-mono text-terminal-green/60 text-xs sm:text-sm mb-8">
              The application failed to start. This is not caused by the page
              you were on.
            </p>

            {process.env.NODE_ENV !== "production" && (
              <pre className="font-terminal-mono text-xs text-terminal-danger/70 bg-terminal-black border border-terminal-danger/20 p-4 mb-6 overflow-x-auto whitespace-pre-wrap">
                {error.message}
                {error.digest ? `\n\ndigest: ${error.digest}` : ""}
              </pre>
            )}

            <div className="flex flex-wrap gap-3">
              <Button variant="primary" size="default" onClick={() => reset()}>
                Retry
              </Button>
              <Button
                variant="secondary"
                size="default"
                onClick={() => reloadPage()}
              >
                Reload page
              </Button>
            </div>
          </div>
        </div>
      </body>
    </html>
  )
}