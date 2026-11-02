import { useQuery } from '@tanstack/react-query'
import clsx from 'clsx'
import { ChevronLeft, ChevronRight } from 'lucide-react'
import { useState } from 'react'
import { Button, Card, Empty, ErrorBox, PageHeader, Spinner } from '../components/ui'
import { api } from '../lib/api'
import { daysInMonth, fmtMonth, monthStart, shiftMonth, todayISO } from '../lib/format'
import { useI18n } from '../lib/i18n'

export default function TeamCalendar() {
  const { t, lang } = useI18n()
  const [month, setMonth] = useState(monthStart(todayISO()))
  const days = daysInMonth(month)
  const end = month.slice(0, 8) + String(days).padStart(2, '0')
  const q = useQuery<any[]>({ queryKey: ['team', month], queryFn: () => api.teamCalendar(month, end) })
  const people: Record<string, { name: string; rows: any[] }> = {}
  for (const r of q.data ?? []) (people[r.employee] ??= { name: r.employee_name, rows: [] }).rows.push(r)
  const covers = (r: any, iso: string) => r.from_date <= iso && r.to_date >= iso
  return (
    <div>
      <PageHeader title={t('Team Calendar')} subtitle={t('Who is out')} />
      <Card
        title={fmtMonth(month, lang)}
        action={<div className="flex gap-1">
          <Button variant="secondary" size="sm" onClick={() => setMonth(shiftMonth(month, -1))}><ChevronLeft className="size-4 flip-rtl" /></Button>
          <Button variant="secondary" size="sm" onClick={() => setMonth(shiftMonth(month, 1))}><ChevronRight className="size-4 flip-rtl" /></Button>
        </div>}
      >
        {q.isLoading ? <Spinner /> : q.error ? <ErrorBox error={q.error} /> : !Object.keys(people).length ? <Empty title={t('All caught up')} /> : (
          <div className="overflow-x-auto">
            <table className="w-full border-separate border-spacing-0.5 text-xs">
              <thead>
                <tr>
                  <th className="sticky start-0 bg-white px-2 text-start font-medium text-muted">{t('Employee')}</th>
                  {Array.from({ length: days }).map((_, i) => <th key={i} className="w-7 text-center font-normal text-muted tabular-nums">{i + 1}</th>)}
                </tr>
              </thead>
              <tbody>
                {Object.entries(people).map(([id, p]) => (
                  <tr key={id}>
                    <td className="sticky start-0 whitespace-nowrap bg-white px-2 py-1 font-medium">{p.name}</td>
                    {Array.from({ length: days }).map((_, i) => {
                      const iso = month.slice(0, 8) + String(i + 1).padStart(2, '0')
                      const r = p.rows.find((x) => covers(x, iso))
                      return <td key={i} title={r ? `${r.leave_type} · ${t(r.status)}` : ''} className={clsx('h-7 rounded', r ? (r.status === 'Approved' ? 'bg-brand' : 'bg-amber-300') : 'bg-surface')} />
                    })}
                  </tr>
                ))}
              </tbody>
            </table>
            <div className="mt-3 flex gap-4 text-xs text-muted">
              <span className="flex items-center gap-1.5"><span className="size-3 rounded bg-brand" />{t('Approved')}</span>
              <span className="flex items-center gap-1.5"><span className="size-3 rounded bg-amber-300" />{t('Open')}</span>
            </div>
          </div>
        )}
      </Card>
    </div>
  )
}
