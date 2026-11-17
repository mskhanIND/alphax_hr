// A short, in-memory trail used by "Report a problem": the last errors shown and the last pages visited.
// Nothing here leaves the browser unless the user sends a report.

interface ErrorEntry { at: number; where: string; message: string }

const errors: ErrorEntry[] = []
const pages: string[] = []
const KEEP_MS = 30 * 60 * 1000

export function recordError(where: string, message: unknown) {
  const text = String((message as any)?.message ?? message ?? '').trim()
  if (!text) return
  errors.push({ at: Date.now(), where, message: text.slice(0, 1500) })
  while (errors.length > 8) errors.shift()
}

export function recordPage(path: string) {
  if (pages[pages.length - 1] === path) return
  pages.push(path)
  while (pages.length > 6) pages.shift()
}

export function recentErrors(): string {
  const since = Date.now() - KEEP_MS
  return errors
    .filter((e) => e.at >= since)
    .map((e) => `${new Date(e.at).toLocaleTimeString()} · ${e.where}\n${e.message}`)
    .join('\n\n')
}

export function recentPages(): string {
  return pages.slice(0, -1).join(' → ')
}

let installed = false
export function installErrorTrail() {
  if (installed || typeof window === 'undefined') return
  installed = true
  window.addEventListener('error', (e) => recordError('page script', e.message))
  window.addEventListener('unhandledrejection', (e) => recordError('page script', e.reason))
}
