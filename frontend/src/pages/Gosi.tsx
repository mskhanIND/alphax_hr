import { useQuery } from '@tanstack/react-query'
import { ChevronLeft, ChevronRight, Download } from 'lucide-react'
import { useState } from 'react'
import { Link } from 'react-router-dom'
import { Badge, Button, Card, ErrorBox, PageHeader, Spinner, Stat, Table } from '../components/ui'
import { api } from '../lib/api'
import { fmtMoney, fmtMonth, fmtNumber, monthStart, shiftMonth, todayISO } from '../lib/format'
import { useI18n } from '../lib/i18n'

function toCsv(rows: any[]) {
  const head = ['employee', 'employee_name', 'gosi_number', 'system', 'wage', 'employee_rate', 'employer_rate', 'employee_amount', 'employer_amount', 'total', 'warnings']
  const esc = (v: any) => `"${String(v ?? '').replace(/"/g, '""')}"`
  return [head.join(','), ...rows.map((r) => head.map((h) => esc(Array.isArray(r[h]) ? r[h].join('; ') : r[h])).join(','))].join('\n')
}

export default function Gosi() {
  const { t, lang } = useI18n()
  const [month, setMonth] = useState(monthStart(todayISO()))
  const q = useQuery<any>({ queryKey: ['gosi', month], queryFn: () => api.gosiRegister(month) })
  const download = () => {
    const blob = new Blob(['﻿' + toCsv(q.data.rows)], { type: 'text/csv;charset=utf-8' })
    const a = document.createElement('a')
    a.href = URL.createObjectURL(blob)
    a.download = `gosi-${month.slice(0, 7)}.csv`
    a.click()
    URL.revokeObjectURL(a.href)
  }
  return (
    <div className="flex flex-col gap-5">
      <PageHeader title={t('GOSI Register')} actions={
        <div className="flex items-center gap-2">
          <Button variant="secondary" size="sm" onClick={() => setMonth(shiftMonth(month, -1))}><ChevronLeft className="size-4 flip-rtl" /></Button>
          <span className="min-w-32 text-center text-sm font-medium">{fmtMonth(month, lang)}</span>
          <Button variant="secondary" size="sm" onClick={() => setMonth(shiftMonth(month, 1))}><ChevronRight className="size-4 flip-rtl" /></Button>
          <Button variant="secondary" size="sm" disabled={!q.data} onClick={download}><Download className="size-4" />CSV</Button>
        </div>} />
      {q.isLoading ? <Spinner /> : q.error ? <ErrorBox error={q.error} onRetry={() => q.refetch()} /> : (
        <>
          <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">
            <Stat label={t('Employee share')} value={fmtMoney(q.data.totals.employee, lang)} />
            <Stat label={t('Employer share')} value={fmtMoney(q.data.totals.employer, lang)} />
            <Stat label={t('Total')} value={fmtMoney(q.data.totals.total, lang)} tone="blue" />
            <Stat label={t('Needs attention')} value={fmtNumber(q.data.needs_attention, lang)} tone={q.data.needs_attention ? 'amber' : 'brand'} />
          </div>
          <div className="flex flex-wrap gap-2">
            {Object.entries(q.data.systems).map(([s, n]) => <Badge key={s} tone={s === 'Unclassified' ? 'amber' : 'gray'}>{t(s)}: {String(n)}</Badge>)}
          </div>
          <Card>
            <Table head={[t('Employee'), t('System'), t('Contributory wage'), t('Employee share'), t('Employer share'), t('Warnings')]}>
              {q.data.rows.map((r: any) => (
                <tr key={r.employee}>
                  <td className="px-3 py-2"><Link className="font-medium text-brand hover:underline" to={`/people/${encodeURIComponent(r.employee)}`}>{r.employee_name}</Link><div className="text-xs text-muted">{r.gosi_number || r.employee}</div></td>
                  <td className="px-3 py-2"><Badge tone={r.system === 'Unclassified' ? 'amber' : r.system === 'New' ? 'blue' : 'gray'}>{t(r.system)}</Badge></td>
                  <td className="px-3 py-2 tabular-nums">{fmtMoney(r.wage, lang)}</td>
                  <td className="px-3 py-2 tabular-nums">{fmtMoney(r.employee_amount, lang)} <span className="text-xs text-muted">{r.employee_rate}%</span></td>
                  <td className="px-3 py-2 tabular-nums">{fmtMoney(r.employer_amount, lang)} <span className="text-xs text-muted">{r.employer_rate}%</span></td>
                  <td className="px-3 py-2"><div className="flex flex-wrap gap-1">{r.warnings.map((w: string) => <Badge key={w} tone="amber">{t(w)}</Badge>)}</div></td>
                </tr>
              ))}
            </Table>
          </Card>
        </>
      )}
    </div>
  )
}
