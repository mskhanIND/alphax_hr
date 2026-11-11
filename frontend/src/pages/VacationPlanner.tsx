import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import clsx from 'clsx'
import { CalendarRange } from 'lucide-react'
import { useState } from 'react'
import { Button, Card, Empty, ErrorBox, Modal, PageHeader, Select, Spinner, Stat, StatusBadge, Textarea } from '../components/ui'
import { api } from '../lib/api'
import { fmtDate, fmtNumber } from '../lib/format'
import { useI18n } from '../lib/i18n'

function heat(pct: number, over: boolean) {
  if (over) return 'bg-red-500 text-white'
  if (pct >= 20) return 'bg-amber-400'
  if (pct > 0) return 'bg-emerald-200'
  return 'bg-surface'
}

export default function VacationPlanner() {
  const { t, lang } = useI18n()
  const qc = useQueryClient()
  const thisYear = new Date().getFullYear()
  const [year, setYear] = useState(new Date().getMonth() >= 9 ? thisYear + 1 : thisYear)
  const [dept, setDept] = useState('')
  const q = useQuery({ queryKey: ['vacation-planner', year, dept], queryFn: () => api.vacationPlanner(year, dept || undefined) })
  const [act, setAct] = useState<{ plan: any; action: string } | null>(null)
  const [note, setNote] = useState('')
  const m = useMutation({ mutationFn: () => api.act('AlphaX Leave Plan', act!.plan.name, act!.action, note || undefined),
    onSuccess: () => { setAct(null); setNote(''); qc.invalidateQueries({ queryKey: ['vacation-planner'] }); qc.invalidateQueries({ queryKey: ['inbox'] }) } })
  const d = q.data
  const counts = (s: string) => d?.plans.filter((p: any) => p.status === s).length ?? 0
  const [pstatus, setPstatus] = useState('')
  const pick = (k: string) => setPstatus((x) => (x === k ? '' : k))
  return (
    <div className="flex flex-col gap-5">
      <PageHeader title={t('Vacation planner')} subtitle={t('Annual vacation plans and how many people are away each week')}
        actions={<div className="flex gap-2">
          <Select className="w-28" value={year} onChange={(e) => setYear(Number(e.target.value))}>{[thisYear, thisYear + 1].map((x) => <option key={x} value={x}>{x}</option>)}</Select>
          {d?.departments?.length > 1 && <Select className="w-48" value={dept} onChange={(e) => setDept(e.target.value)}>
            <option value="">{t('All departments')}</option>{d.departments.map((x: string) => <option key={x} value={x}>{x}</option>)}</Select>}
        </div>} />
      {q.isLoading ? <Spinner /> : q.error ? <ErrorBox error={q.error} /> : d && (
        <>
          <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">
            <Stat label={t('Waiting for approval')} value={counts('Submitted')} tone="amber" onClick={() => pick('Submitted')} active={pstatus === 'Submitted'} />
            <Stat label={t('Approved')} value={counts('Approved')} tone="brand" onClick={() => pick('Approved')} active={pstatus === 'Approved'} />
            <Stat label={t('Changes requested')} value={counts('Changes requested')} tone="blue" onClick={() => pick('Changes requested')} active={pstatus === 'Changes requested'} />
            {d.not_planned !== null && <Stat label={t('Not planned yet')} value={d.not_planned} tone="red" />}
          </div>
          {d.departments.length > 0 && (
            <Card title={t('Away per week')} subtitle={d.max_off_percent ? `${t('Red = above')} ${d.max_off_percent}% ${t('of the department')}` : undefined}>
              <div className="overflow-x-auto">
                <table className="text-[11px]">
                  <thead><tr><th className="sticky start-0 bg-white pe-2 text-start font-medium">{t('Department')}</th>
                    {d.weeks.map((w: any) => <th key={w.week} className="px-0.5 font-normal text-muted">{w.week.slice(8, 10) <= '07' ? fmtDate(w.week, lang, { month: 'short' }) : ''}</th>)}</tr></thead>
                  <tbody>
                    {d.departments.map((dep: string) => (
                      <tr key={dep}>
                        <td className="sticky start-0 whitespace-nowrap bg-white py-1 pe-2">{dep} <span className="text-muted">({d.headcount[dep]})</span></td>
                        {d.weeks.map((w: any) => {
                          const c = w.by_department[dep]
                          return <td key={w.week} className="px-0.5"><div title={c.off ? `${fmtDate(w.week, lang)}: ${c.names.join(', ')}` : fmtDate(w.week, lang)}
                            className={clsx('grid h-6 w-6 place-items-center rounded', heat(c.percent, c.over_limit))}>{c.off || ''}</div></td>
                        })}
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </Card>
          )}
          <Card title={t('Plans')}>
            {!d.plans.length ? <Empty title={t('No plans yet')} icon={<CalendarRange />}>{t('Employees plan their vacation from Services → Vacation plan.')}</Empty> : (
              <ul className="divide-y divide-line">
                {d.plans.filter((p: any) => !pstatus || p.status === pstatus).map((p: any) => (
                  <li key={p.name} className="flex flex-wrap items-center gap-3 py-3">
                    <div className="min-w-0 flex-1">
                      <div className="flex flex-wrap items-center gap-2"><span className="font-medium">{p.employee_name}</span><StatusBadge status={p.status} />
                        <span className="text-xs text-muted">{p.department} · {fmtNumber(p.total_days, lang, 0)}/{fmtNumber(p.entitlement, lang, 0)} {t('days')}</span></div>
                      <div className="text-sm text-muted">{p.periods.map((x: any) => `${fmtDate(x.from_date, lang)} → ${fmtDate(x.to_date, lang)}`).join(' · ')}</div>
                    </div>
                    {p.actions.map((a: string) => <Button key={a} size="sm" variant={a === 'Approve' ? 'primary' : 'secondary'} onClick={() => setAct({ plan: p, action: a })}>{t(a)}</Button>)}
                  </li>
                ))}
              </ul>
            )}
          </Card>
        </>
      )}
      <Modal open={!!act} onClose={() => setAct(null)} title={act ? `${t(act.action)} · ${act.plan.employee_name}` : ''}
        footer={<><Button variant="secondary" onClick={() => setAct(null)}>{t('Cancel')}</Button>
          <Button loading={m.isPending} disabled={act?.action !== 'Approve' && !note.trim()} onClick={() => m.mutate()}>{act ? t(act.action) : ''}</Button></>}>
        <Textarea placeholder={act?.action === 'Approve' ? t('Comment (optional)') : t('Tell the employee what to change')} value={note} onChange={(e) => setNote(e.target.value)} />
        {m.error && <div className="mt-3"><ErrorBox error={m.error} /></div>}
      </Modal>
    </div>
  )
}
