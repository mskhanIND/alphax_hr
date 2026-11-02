import { readFileSync, readdirSync, statSync } from 'node:fs'
import { join } from 'node:path'
import { describe, expect, it } from 'vitest'
import { daysInMonth, initials, monthStart, shiftMonth, todayISO } from './format'

describe('dates are Riyadh business dates', () => {
  it('uses Asia/Riyadh, not UTC (regression: portal showed yesterday after 9pm)', () => {
    // 2 Nov 2026 00:30 Riyadh == 1 Nov 2026 21:30 UTC
    expect(todayISO(new Date('2026-11-01T21:30:00Z'))).toBe('2026-11-02')
    expect(todayISO(new Date('2026-11-01T20:59:00Z'))).toBe('2026-11-01')
  })
  it('month helpers', () => {
    expect(monthStart('2026-11-17')).toBe('2026-11-01')
    expect(shiftMonth('2026-01-01', -1)).toBe('2025-12-01')
    expect(shiftMonth('2026-12-01', 1)).toBe('2027-01-01')
    expect(daysInMonth('2028-02-01')).toBe(29)
  })
  it('initials', () => {
    expect(initials('Bushra Muteb Alharbi')).toBe('BA')
    expect(initials(null)).toBe('?')
  })
})

describe('Arabic coverage', () => {
  it('every literal t("...") used in the UI has an Arabic translation', async () => {
    const { arabicKeys } = await import('./i18n')
    const keys = new Set(arabicKeys)
    const root = join(__dirname, '..')
    const files: string[] = []
    const walk = (d: string) => readdirSync(d).forEach((f) => {
      const p = join(d, f)
      if (statSync(p).isDirectory()) walk(p)
      else if (p.endsWith('.tsx')) files.push(p)
    })
    walk(root)
    const missing = new Set<string>()
    for (const f of files) {
      const src = readFileSync(f, 'utf8')
      for (const m of src.matchAll(/\bt\('([^']+)'\)/g)) if (!keys.has(m[1])) missing.add(m[1])
    }
    expect([...missing]).toEqual([])
  })
})
