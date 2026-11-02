import { useQuery } from '@tanstack/react-query'
import { ChevronLeft, ChevronRight, Landmark, Users, Wallet } from 'lucide-react'
import { useState } from 'react'
import { Button, Card, Empty, ErrorBox, PageHeader, Spinner, Stat, StatusBadge, Table } from '../components/ui'
import { api } from '../lib/api'
import { fmtDate, fmtMoney, fmtMonth, fmtNumber, monthStart, shiftMonth, todayISO } from '../lib/format'
import { useI18n } from '../lib/i18n'

export default function Payroll() {
  const { t, lang } = useI18n()
  const [month, setMonth] = useState(monthStart(todayISO()))
  const year = Number(month.slice(0, 4))
  const sum = useQuery<any>({ queryKey: ['slipSummary', month], queryFn: () => api.slipSummary(month) })
  const [scope, setScope] = useState<'month' | 'year'>('month')
  const runs = useQuery<any>({ queryKey: ['payrollRuns', scope, scope === 'month' ? month : year], queryFn: () => api.payrollRuns(year, scope === 'month' ? month : undefined) })
  const sub = sum.data?.submitted ?? {}
  const draft = sum.data?.draft ?? {}
  return (
    <div className="flex flex-col gap-5">
      <PageHeader title={t('Payroll')} actions={
        <div className="flex items-center gap-2">
          <Button variant="secondary" size="sm" onClick={() => setMonth(shiftMonth(month, -1))}><ChevronLeft className="size-4 flip-rtl" /></Button>
          <span className="min-w-32 text-center text-sm font-medium">{fmtMonth(month, lang)}</span>
          <Button variant="secondary" size="sm" onClick={() => setMonth(shiftMonth(month, 1))}><ChevronRight className="size-4 flip-rtl" /></Button>
        </div>} />
      {sum.error && <ErrorBox error={sum.error} />}
      <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">
        <Stat label={t('Active employees')} value={fmtNumber(sum.data?.active_employees, lang)} icon={<Users className="size-4" />} />
        <Stat label={`${t('Slips')} · ${t('Submitted')}`} value={fmtNumber(sub.slips ?? 0, lang)} hint={draft.slips ? `${t('Draft')}: ${draft.slips}` : undefined} icon={<Wallet className="size-4" />} tone="blue" />
        <Stat label={t('Gross pay')} value={fmtMoney(sub.gross ?? 0, lang)} icon={<Landmark className="size-4" />} />
        <Stat label={t('Net pay')} value={fmtMoney(sub.net ?? 0, lang)} icon={<Landmark className="size-4" />} tone="amber" />
      </div>
      <Card title={`${t('Payroll runs')} · ${scope === 'month' ? fmtMonth(month, lang) : year}`}
        action={<div className="flex rounded-xl border border-line p-0.5" role="tablist">
          {(['month', 'year'] as const).map((v) => (
            <button key={v} role="tab" aria-selected={scope === v} onClick={() => setScope(v)}
              className={`rounded-lg px-3 py-1 text-sm ${scope === v ? 'bg-brand text-white' : 'text-muted hover:bg-surface'}`}>{t(v === 'month' ? 'This month' : 'Whole year')}</button>
          ))}
        </div>}>
        {runs.isLoading ? <Spinner /> : runs.error ? <ErrorBox error={runs.error} /> : !runs.data.rows.length ? <Empty title={t('No payroll runs for this period')} /> : (
          <Table head={[t('Month'), t('Company'), t('Employee'), t('Status')]}>
            {runs.data.rows.map((r: any) => (
              <tr key={r.name}>
                <td className="px-3 py-2"><div className="font-medium">{fmtDate(r.start_date, lang)} → {fmtDate(r.end_date, lang)}</div><div className="text-xs text-muted">{r.name}</div></td>
                <td className="px-3 py-2">{r.company}{r.department ? ` · ${r.department}` : ''}</td>
                <td className="px-3 py-2 tabular-nums">{r.number_of_employees}</td>
                <td className="px-3 py-2"><StatusBadge status={r.status} /></td>
              </tr>
            ))}
          </Table>
        )}
      </Card>
    </div>
  )
}
