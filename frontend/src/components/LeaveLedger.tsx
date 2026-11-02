import { useQuery } from '@tanstack/react-query'
import clsx from 'clsx'
import { useState } from 'react'
import { api } from '../lib/api'
import { fmtDate, fmtNumber } from '../lib/format'
import { useI18n } from '../lib/i18n'
import { Card, ErrorBox, Spinner } from './ui'

const TX_LABEL: Record<string, string> = {
  'Leave Allocation': 'Allocated', 'Leave Application': 'Leave taken', 'Leave Encashment': 'Encashed', 'Compensatory Leave Request': 'Compensatory',
}

/** Balances per leave type, the Art. 117 sick-leave year, and the ledger with running balances. */
export function LeaveLedger({ employee, compact }: { employee?: string; compact?: boolean }) {
  const { t, lang } = useI18n()
  const q = useQuery<any>({ queryKey: ['leaveSummary', employee ?? 'me'], queryFn: () => api.leaveSummary(employee) })
  const [type, setType] = useState('')
  const [showAll, setShowAll] = useState(false)
  if (q.isLoading) return <Spinner />
  if (q.error) return <ErrorBox error={q.error} onRetry={() => q.refetch()} />
  const d = q.data
  const ledger = (d.ledger as any[]).filter((e) => !type || e.leave_type === type)
  return (
    <div className="flex flex-col gap-4">
      <div className={clsx('grid gap-3', compact ? 'grid-cols-2' : 'sm:grid-cols-2 lg:grid-cols-4')}>
        {d.balances.map((b: any) => (
          <button key={b.leave_type} onClick={() => setType(type === b.leave_type ? '' : b.leave_type)}
            className={clsx('rounded-xl border p-3 text-start', type === b.leave_type ? 'border-brand bg-brand-50' : 'border-line hover:bg-surface')}>
            <div className="truncate text-sm text-muted">{b.leave_type}</div>
            <div className="text-2xl font-semibold tabular-nums">{fmtNumber(b.balance, lang, 1)}</div>
            <div className="text-xs text-muted">{t('Allocated')} {fmtNumber(b.allocated, lang, 1)} · {t('Taken')} {fmtNumber(b.taken, lang, 1)}{b.pending ? ` · ${t('Pending')} ${fmtNumber(b.pending, lang, 1)}` : ''}</div>
          </button>
        ))}
      </div>
      {d.sick && (
        <div className="rounded-xl border border-line p-3">
          <div className="mb-2 flex flex-wrap items-baseline justify-between gap-2">
            <span className="text-sm font-medium">{t('Sick leave (Art. 117)')}</span>
            <span className="text-xs text-muted">{d.sick.cycle_start ? `${t('Sick-leave year')} ${fmtDate(d.sick.cycle_start, lang)} → ${fmtDate(d.sick.cycle_end, lang)}` : t('No sick leave in the last year')}</span>
          </div>
          <div className="flex h-3 overflow-hidden rounded-full bg-surface" title={`${d.sick.used} / 120`}>
            {d.sick.tiers.map((tier: any, i: number) => (
              <div key={i} style={{ width: `${(100 * tier.days) / 120}%` }} className="relative border-e border-white last:border-0">
                <div className={clsx('h-full', ['bg-emerald-500', 'bg-amber-400', 'bg-slate-400'][i])} style={{ width: `${(100 * (tier.days - tier.left)) / tier.days}%` }} />
              </div>
            ))}
          </div>
          <div className="mt-2 grid grid-cols-3 gap-2 text-xs">
            {d.sick.tiers.map((tier: any, i: number) => (
              <div key={i}><span className={clsx('me-1 inline-block size-2 rounded-full', ['bg-emerald-500', 'bg-amber-400', 'bg-slate-400'][i])} />
                {t(['Full pay', '75% pay', 'Unpaid'][i])}: <b className="tabular-nums">{fmtNumber(tier.left, lang)}</b> / {tier.days} {t('left')}</div>
            ))}
          </div>
        </div>
      )}
      <Card title={`${t('Leave ledger')}${type ? ` · ${type}` : ''}`} className="!p-0 !shadow-none !border-0">
        {!ledger.length ? <p className="text-sm text-muted">{t('No entries yet.')}</p> : (
          <div className="overflow-x-auto">
            <table className="w-full whitespace-nowrap text-sm">
              <thead className="text-xs text-muted"><tr className="border-b border-line">
                {['Date', 'Leave type', 'Entry', 'Days', 'Balance'].map((h) => <th key={h} className="px-2 pb-2 text-start font-medium">{t(h)}</th>)}
              </tr></thead>
              <tbody className="divide-y divide-line">
                {(showAll ? ledger : ledger.slice(0, 12)).map((e: any, i: number) => (
                  <tr key={i}>
                    <td className="px-2 py-1.5">{fmtDate(e.from_date, lang)}{e.to_date && e.to_date !== e.from_date ? ` → ${fmtDate(e.to_date, lang)}` : ''}</td>
                    <td className="px-2 py-1.5">{e.leave_type}</td>
                    <td className="px-2 py-1.5">{t(e.is_expired ? 'Expired' : e.is_carry_forward ? 'Carried forward' : TX_LABEL[e.transaction_type] ?? e.transaction_type)}
                      <span className="ms-1 text-xs text-muted">{e.transaction_name}</span></td>
                    <td className={clsx('px-2 py-1.5 tabular-nums font-medium', e.leaves < 0 ? 'text-red-700' : 'text-emerald-700')}>{e.leaves > 0 ? '+' : ''}{fmtNumber(e.leaves, lang, 1)}</td>
                    <td className="px-2 py-1.5 tabular-nums">{fmtNumber(e.balance, lang, 1)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
            {ledger.length > 12 && <button className="mt-2 text-sm text-brand hover:underline" onClick={() => setShowAll((x) => !x)}>{showAll ? t('Show less') : `${t('Show all')} (${ledger.length})`}</button>}
          </div>
        )}
      </Card>
    </div>
  )
}
