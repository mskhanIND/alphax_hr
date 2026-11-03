import { call } from './api'

const A = 'alphax_hr.api.notify.'

function keyBytes(b64: string) {
  const pad = '='.repeat((4 - (b64.length % 4)) % 4)
  const raw = atob((b64 + pad).replace(/-/g, '+').replace(/_/g, '/'))
  return Uint8Array.from([...raw].map((c) => c.charCodeAt(0)))
}

export function pushSupported() {
  return typeof window !== 'undefined' && window.isSecureContext && 'serviceWorker' in navigator && 'PushManager' in window && 'Notification' in window
}

export async function currentSubscription() {
  if (!pushSupported()) return null
  const reg = await navigator.serviceWorker.getRegistration('/alphax')
  return reg ? reg.pushManager.getSubscription() : null
}

/** Ask permission, subscribe this device and register it with the server. */
export async function enablePush() {
  if (!pushSupported()) throw new Error('This browser cannot receive notifications. On iPhone, add AlphaX to the home screen first.')
  const perm = await Notification.requestPermission()
  if (perm !== 'granted') throw new Error('Notifications are blocked for this site in the browser settings.')
  const reg = (await navigator.serviceWorker.getRegistration('/alphax')) ??
    (await navigator.serviceWorker.register('/api/method/alphax_hr.api.pwa.service_worker', { scope: '/alphax' }))
  await navigator.serviceWorker.ready
  const { key } = await call<{ key: string }>(A + 'public_key')
  let sub = await reg.pushManager.getSubscription()
  if (!sub) sub = await reg.pushManager.subscribe({ userVisibleOnly: true, applicationServerKey: keyBytes(key) })
  await call(A + 'subscribe', { subscription: sub.toJSON(), device: navigator.userAgent.slice(0, 120) })
  return sub
}

export async function disablePush() {
  const sub = await currentSubscription()
  if (sub) {
    await call(A + 'unsubscribe', { endpoint: sub.endpoint })
    await sub.unsubscribe()
  }
}

export const sendTestPush = () => call<{ sent: number }>(A + 'test')
