import { useQuery } from '@tanstack/react-query'
import { api } from '../lib/api'
import { useI18n } from '../lib/i18n'
import { Select } from './ui'

/** Saudi banks with their abbreviation (the bank also follows the IBAN when it is saved). */
export function BankSelect({ value, onChange, className }: { value: string; onChange: (v: string) => void; className?: string }) {
  const { lang } = useI18n()
  const q = useQuery({ queryKey: ['banks'], queryFn: api.banks, staleTime: 3_600_000 })
  const list: any[] = q.data ?? []
  return (
    <Select value={value ?? ''} className={className} onChange={(e) => onChange(e.target.value)} data-testid="bank-select">
      <option value="">—</option>
      {value && !list.some((b) => b.name === value) && <option value={value}>{value}</option>}
      {list.map((b) => <option key={b.name} value={b.name}>{b.abbr ? `${b.abbr} — ` : ''}{lang === 'ar' && b.name_ar ? b.name_ar : b.name}</option>)}
    </Select>
  )
}
