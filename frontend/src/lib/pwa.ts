import { useEffect, useState } from 'react'

/** Register the service worker (production build only) so AlphaX can be installed and opens offline. */
export function registerServiceWorker() {
  if (import.meta.env.DEV || !('serviceWorker' in navigator)) return
  window.addEventListener('load', () => {
    navigator.serviceWorker.register('/api/method/alphax_hr.api.pwa.service_worker', { scope: '/alphax' }).catch(() => { /* optional */ })
  })
}

type PromptEvent = Event & { prompt: () => Promise<void>; userChoice: Promise<{ outcome: string }> }
let deferred: PromptEvent | null = null
const listeners = new Set<() => void>()
if (typeof window !== 'undefined') {
  window.addEventListener('beforeinstallprompt', (e) => { e.preventDefault(); deferred = e as PromptEvent; listeners.forEach((l) => l()) })
  window.addEventListener('appinstalled', () => { deferred = null; listeners.forEach((l) => l()) })
}

export function isStandalone() {
  return window.matchMedia?.('(display-mode: standalone)').matches || (navigator as any).standalone === true
}
export function isIOS() {
  return /iphone|ipad|ipod/i.test(navigator.userAgent) && !(window as any).MSStream
}

/** Android/desktop: a real install prompt. iOS: instructions (Share → Add to Home Screen). */
export function useInstall() {
  const [, force] = useState(0)
  useEffect(() => { const l = () => force((n) => n + 1); listeners.add(l); return () => { listeners.delete(l) } }, [])
  const standalone = isStandalone()
  return {
    canPrompt: !!deferred && !standalone,
    showIOSHint: isIOS() && !standalone,
    install: async () => { if (!deferred) return; await deferred.prompt(); deferred = null; force((n) => n + 1) },
  }
}
