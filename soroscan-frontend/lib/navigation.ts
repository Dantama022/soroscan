/**
 * Thin wrappers around browser navigation so components stay testable
 * (jsdom's window.location cannot be redefined or spied on).
 */
export function hardNavigate(url: string): void {
  if (typeof window !== "undefined") {
    window.location.href = url
  }
}

export function reloadPage(): void {
  if (typeof window !== "undefined") {
    window.location.reload()
  }
}
