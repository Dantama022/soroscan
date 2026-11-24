import Link from "next/link"
import { Button } from "@/components/terminal/Button"

/**
 * Custom 404 page for unmatched routes (issue #1707).
 *
 * Rendered by the App Router whenever `notFound()` is called or when no route
 * matches the request. Styled with the existing terminal UI primitives so the
 * 404 page feels like part of the product rather than a framework default.
 */
export default function NotFound() {
  return (
    <div className="min-h-screen flex items-center justify-center px-4 py-16 bg-terminal-black">
      <div className="w-full max-w-2xl">
        <div className="border-terminal border-terminal-green/40 bg-terminal-black p-8 sm:p-12">
          <p className="font-terminal-mono text-terminal-green/60 text-sm tracking-widest mb-4">
            ERROR 404
          </p>

          <h1 className="font-terminal-mono text-terminal-green text-3xl sm:text-5xl font-bold mb-6">
            Route not found
          </h1>

          <p className="font-terminal-mono text-terminal-green/80 text-sm sm:text-base mb-2">
            <span className="text-terminal-cyan">$</span> soroscan resolve{" "}
            <span className="text-terminal-danger">&lt;unknown-route&gt;</span>
          </p>
          <p className="font-terminal-mono text-terminal-green/60 text-xs sm:text-sm mb-8">
            The page you requested does not exist or has been moved.
          </p>

          <div className="flex flex-wrap gap-3">
            <Link href="/">
              <Button variant="primary" size="default">
                Return home
              </Button>
            </Link>
            <Link href="/dashboard">
              <Button variant="secondary" size="default">
                Open dashboard
              </Button>
            </Link>
          </div>
        </div>

        <p className="font-terminal-mono text-terminal-green/40 text-xs mt-6 text-center">
          If you followed a link to get here, the destination may have moved.
        </p>
      </div>
    </div>
  )
}