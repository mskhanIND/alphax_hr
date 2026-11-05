// Dates are business dates in Saudi Arabia: always compute "today" in Asia/Riyadh,
// never via toISOString() (which is UTC and is a day behind after 9pm Riyadh time).
export const TIMEZONE = 'Asia/Riyadh'

export function todayISO(now: Date = new Date(), tz = TIMEZONE): string {
  const parts = new Intl.DateTimeFormat('en-CA', { timeZone: tz, year: 'numeric', month: '2-digit', day: '2-digit' }).formatToParts(now)
  const get = (t: string) => parts.find((p) => p.type === t)!.value
  return `${get('year')}-${get('month')}-${get('day')}`
}

export function monthStart(iso: string): string {
  return iso.slice(0, 8) + '01'
}

export function shiftMonth(iso: string, delta: number): string {
  const [y, m] = iso.split('-').map(Number)
  const d = new Date(Date.UTC(y, m - 1 + delta, 1))
  return `${d.getUTCFullYear()}-${String(d.getUTCMonth() + 1).padStart(2, '0')}-01`
}

export function daysInMonth(iso: string): number {
  const [y, m] = iso.split('-').map(Number)
  return new Date(Date.UTC(y, m, 0)).getUTCDate()
}

const loc = (lang: string) => (lang === 'ar' ? 'ar-SA-u-ca-gregory-nu-latn' : 'en-GB')

export function fmtDate(value: string | null | undefined, lang = 'en', opts: Intl.DateTimeFormatOptions = { day: '2-digit', month: 'short', year: 'numeric' }) {
  if (!value) return '—'
  const [y, m, d] = value.slice(0, 10).split('-').map(Number)
  if (!y) return value
  return new Intl.DateTimeFormat(loc(lang), { ...opts, timeZone: 'UTC' }).format(new Date(Date.UTC(y, m - 1, d)))
}

export function fmtMonth(value: string, lang = 'en') {
  return fmtDate(value, lang, { month: 'long', year: 'numeric' })
}

/** "05 Nov 2026 08:01" from "2026-11-05 08:01:10" (server local time, shown as is). */
export function fmtDateTime(value: string | null | undefined, lang = 'en') {
  if (!value) return '—'
  return `${fmtDate(value, lang)} ${value.slice(11, 16)}`
}

export function fmtTime(value: string | null | undefined) {
  if (!value) return '—'
  return value.slice(11, 16)
}

export function fmtMoney(value: number | null | undefined, lang = 'en', currency = 'SAR') {
  if (value === null || value === undefined || Number.isNaN(Number(value))) return '—'
  return new Intl.NumberFormat(loc(lang), { style: 'currency', currency, maximumFractionDigits: 2 }).format(Number(value))
}

export function fmtNumber(value: number | null | undefined, lang = 'en', digits = 0) {
  if (value === null || value === undefined) return '—'
  return new Intl.NumberFormat(loc(lang), { maximumFractionDigits: digits }).format(Number(value))
}

export function initials(name?: string | null) {
  if (!name) return '?'
  const parts = name.trim().split(/\s+/)
  return ((parts[0]?.[0] ?? '') + (parts.length > 1 ? parts[parts.length - 1][0] : '')).toUpperCase()
}

/** ISO date ``n`` days after ``iso`` (calendar maths in UTC, so no DST surprises). */
export function addDaysISO(iso: string, n: number): string {
  const d = new Date(iso + 'T00:00:00Z')
  d.setUTCDate(d.getUTCDate() + n)
  return d.toISOString().slice(0, 10)
}

/** Sunday of the week containing ``iso`` (the Saudi working week starts on Sunday). */
export function weekStart(iso: string): string {
  const d = new Date(iso + 'T00:00:00Z')
  return addDaysISO(iso, -d.getUTCDay())
}
