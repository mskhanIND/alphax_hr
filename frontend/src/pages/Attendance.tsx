import { useQuery } from '@tanstack/react-query'
import clsx from 'clsx'
import { ChevronLeft, ChevronRight, Download } from 'lucide-react'
import { useState } from 'react'
import { Button, Card, Empty, ErrorBox, FilterNote, Input, PageHeader, Select, Spinner, Stat } from '../components/ui'
import { api, downloadUrl } from '../lib/api'
import { fmtMoney, fmtMonth, fmtNumber, monthStart, shiftMonth, todayISO } from '../lib/format'
import { useI18n } from '../lib/i18n'

const CODE_STYLE: Record<string, string> = {
  P: 'bg-emerald-500 text-white', A: 'bg-red-500 text-white', L: 'bg-sky-500 text-white', HD: 'bg-amber-400 text-ink',
  W: 'bg-violet-500 text-white', H: 'bg-slate-100 text-slate-500', M: 'bg-orange-500 text-white', '?': 'bg-white text-muted ring-1 ring-line', X: 'bg-slate-300 text-slate-700',
  '': 'bg-transparent',
}
const CODE_LABEL: Record<string, string> = {
  P: 'Present', A: 'Absent', L: 'On leave', HD: 'Half day', W: 'Work from home', H: 'Holiday / weekly off', M: 'Missing punch', '?': 'Not marked yet', X: 'Exempt',
}

export default function Attendance() {
  const { t, lang } = useI18n()
  const [month, setMonth] = useState(monthStart(todayISO()))
  const [department, setDepartment] = useState('')
  const [tab, setTab] = useState<'register' | 'overtime'>('register')
  const deps = useQuery<any>({ queryKey: ['employees', '', 'Active', '', '', 0], queryFn: () => api.employees({ status: 'Active', page_length: 1 }) })
  const reg = useQuery<any>({ queryKey: ['register', month, department], queryFn: () => api.attendanceRegister({ month, department }), enabled: tab === 'register' })
  const ot = useQuery<any>({ queryKey: ['overtime', month, department], queryFn: () => api.overtime({ month, department }), enabled: tab === 'overtime' })
  const rows: any[] = reg.data?.rows ?? []
  const sum = (k: string) => rows.reduce((s, r) => s + (r.totals[k] ?? 0), 0)
  // a tile is a filter: only employees with that measure, most first, and only their matching days highlighted
  const [focus, setFocus] = useState('')
  const [find, setFind] = useState('')
  const FOCUS: Record<string, string> = { A: 'Absent days', late_count: 'Late arrivals', M: 'Missing punches', L: 'Leave days', overtime_hours: 'Overtime hours' }
  const toggle = (k: string) => setFocus((f) => (f === k ? '' : k))
  const shown = rows.filter((r) => (!focus || (r.totals[focus] ?? 0) > 0) && (!find || `${r.employee_name} ${r.employee}`.toLowerCase().includes(find.toLowerCase())))
    .sort((a, b) => (focus ? (b.totals[focus] ?? 0) - (a.totals[focus] ?? 0) : 0))
  const lit = (c: any) => !focus || (focus === 'late_count' ? c.late > 0 : focus === 'overtime_hours' ? c.overtime > 0 : c.code === focus)

  return (
    <div className="flex flex-col gap-5">
      <PageHeader title={t('Attendance')} subtitle={t('From check-ins, attendance records, leave and holidays.')}
        actions={tab === 'register' ? (
          <a href={downloadUrl('attendance.export_register', { month, department, file_format: 'xlsx' })}>
            <Button variant="secondary"><Download className="size-4" />{t('Export')}</Button>
          </a>
        ) : undefined} />
      <div className="flex flex-wrap items-center gap-2">
        <Button variant="secondary" size="sm" aria-label={t('Previous')} onClick={() => setMonth(shiftMonth(month, -1))}><ChevronLeft className="size-4 flip-rtl" /></Button>
        <span className="min-w-36 text-center font-medium">{fmtMonth(month, lang)}</span>
        <Button variant="secondary" size="sm" aria-label={t('Next')} onClick={() => setMonth(shiftMonth(month, 1))}><ChevronRight className="size-4 flip-rtl" /></Button>
        <Select aria-label={t('Department')} className="!w-56" value={department} onChange={(e) => setDepartment(e.target.value)}>
          <option value="">{t('All departments')}</option>
          {(deps.data?.departments ?? []).map((d: string) => <option key={d} value={d}>{d}</option>)}
        </Select>
        <span className="flex-1" />
        <div className="flex rounded-xl border border-line p-0.5" role="tablist">
          {(['register', 'overtime'] as const).map((v) => (
            <button key={v} role="tab" aria-selected={tab === v} onClick={() => setTab(v)}
              className={clsx('rounded-lg px-3 py-1.5 text-sm', tab === v ? 'bg-brand text-white' : 'text-muted hover:bg-surface')}>
              {t(v === 'register' ? 'Register' : 'Overtime')}
            </button>
          ))}
        </div>
      </div>

      {tab === 'register' ? (
        reg.isLoading ? <Spinner /> : reg.error ? <ErrorBox error={reg.error} onRetry={() => reg.refetch()} /> : (
          <>
            <div className="grid grid-cols-2 gap-3 lg:grid-cols-5">
              <Stat label={t('Absent days')} value={fmtNumber(sum('A'), lang)} tone="red" onClick={() => toggle('A')} active={focus === 'A'} />
              <Stat label={t('Late arrivals')} value={fmtNumber(sum('late_count'), lang)} hint={`${fmtNumber(sum('late_minutes'), lang)} ${t('minutes')}`} tone="amber" onClick={() => toggle('late_count')} active={focus === 'late_count'} />
              <Stat label={t('Missing punches')} value={fmtNumber(sum('M'), lang)} tone="amber" onClick={() => toggle('M')} active={focus === 'M'} />
              <Stat label={t('Leave days')} value={fmtNumber(sum('L'), lang)} tone="blue" onClick={() => toggle('L')} active={focus === 'L'} />
              <Stat label={t('Overtime hours')} value={fmtNumber(sum('overtime_hours'), lang, 1)} onClick={() => toggle('overtime_hours')} active={focus === 'overtime_hours'} />
            </div>
            {focus && <FilterNote label={`${t(FOCUS[focus])}: ${t('most first')}`} count={shown.length} onClear={() => setFocus('')} />}
            <Card>
              <Input value={find} onChange={(e) => setFind(e.target.value)} placeholder={t('Search employee')} className="mb-3 !w-64" />
              <div className="mb-3 flex flex-wrap gap-3 text-xs text-muted">
                {Object.entries(CODE_LABEL).map(([c, l]) => (
                  <span key={c} className="flex items-center gap-1.5"><span className={clsx('grid h-5 min-w-5 place-items-center rounded px-1 font-semibold', CODE_STYLE[c])}>{c}</span>{t(l)}</span>
                ))}
                <span className="flex items-center gap-1.5"><span className="size-2 rounded-full bg-amber-500" />{t('Late')}</span>
              </div>
              {!shown.length ? <Empty title={t('No employees found')} /> : (
                <div className="overflow-x-auto">
                  <table className="w-full border-separate border-spacing-0 text-xs">
                    <thead><tr>
                      <th className="sticky start-0 z-10 bg-white pb-2 pe-3 text-start text-sm">{t('Employee')}</th>
                      {reg.data.dates.map((d: string) => <th key={d} className="px-0.5 pb-2 text-center font-medium tabular-nums text-muted">{d.slice(8)}</th>)}
                      {['P', 'A', 'L', 'Late', 'M', 'OT h'].map((h) => <th key={h} className="px-1.5 pb-2 text-center font-semibold">{h.length === 1 ? h : t(h)}</th>)}
                    </tr></thead>
                    <tbody>
                      {shown.map((r) => (
                        <tr key={r.employee}>
                          <td className="sticky start-0 z-10 whitespace-nowrap border-t border-line bg-white py-1 pe-3 text-sm font-medium">{r.employee_name}</td>
                          {r.cells.map((c: any) => (
                            <td key={c.date} className="border-t border-line px-0.5 py-1 text-center"
                              title={[t(CODE_LABEL[c.code] ?? ''), c.shift, c.first_in && `${t('In')} ${c.first_in.slice(11, 16)}`, c.last_out && `${t('Out')} ${c.last_out.slice(11, 16)}`,
                                c.late && `${t('Late')} ${c.late} ${t('min')}`, (c.late_excused || c.early_excused) && `${t('Excused by permission')} ${(c.late_excused || 0) + (c.early_excused || 0)} ${t('min')}`, c.early && `${t('Left early')} ${c.early} ${t('min')}`, c.overtime && `${t('Overtime')} ${c.overtime} h`,
                                c.leave, c.holiday && c.holiday !== 'weekly_off' ? c.holiday : null].filter(Boolean).join(' · ')}>
                              <span className={clsx('relative mx-auto grid h-6 w-7 place-items-center rounded font-semibold', CODE_STYLE[c.code], !lit(c) && 'opacity-25')}>
                                {c.code}
                                {c.late > 0 && <span className="absolute -end-0.5 -top-0.5 size-2 rounded-full bg-amber-500 ring-1 ring-white" />}
                              </span>
                            </td>
                          ))}
                          <td className="border-t border-line px-1.5 text-center tabular-nums">{r.totals.P ?? 0}</td>
                          <td className={clsx('border-t border-line px-1.5 text-center tabular-nums', r.totals.A && 'font-semibold text-red-700')}>{r.totals.A ?? 0}</td>
                          <td className="border-t border-line px-1.5 text-center tabular-nums">{r.totals.L ?? 0}</td>
                          <td className={clsx('border-t border-line px-1.5 text-center tabular-nums', r.totals.late_count && 'text-amber-800')}>{r.totals.late_count ?? 0}</td>
                          <td className={clsx('border-t border-line px-1.5 text-center tabular-nums', r.totals.M && 'text-orange-700')}>{r.totals.M ?? 0}</td>
                          <td className="border-t border-line px-1.5 text-center tabular-nums">{fmtNumber(r.totals.overtime_hours ?? 0, lang, 1)}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}
            </Card>
          </>
        )
      ) : (
        ot.isLoading ? <Spinner /> : ot.error ? <ErrorBox error={ot.error} onRetry={() => ot.refetch()} /> : (
          <Card title={t('Overtime (Art. 107)')} subtitle={t('Each extra hour is paid the hourly wage plus 50% of the hourly basic wage. Hourly = monthly ÷ 30 ÷ 8.')}>
            <div className="mb-4 grid grid-cols-2 gap-3">
              <Stat label={t('Overtime hours')} value={fmtNumber(ot.data.total_hours, lang, 1)} />
              <Stat label={t('Overtime amount')} value={fmtMoney(ot.data.total_amount, lang)} />
            </div>
            {!ot.data.rows.length ? <Empty title={t('No overtime this month')} /> : (
              <div className="overflow-x-auto">
                <table className="w-full whitespace-nowrap text-sm">
                  <thead className="text-xs text-muted"><tr className="border-b border-line">
                    {['Employee', 'Department', 'Hours', 'Days', 'Monthly wage', 'Basic', 'Amount'].map((h) => <th key={h} className="px-2 pb-2 text-start font-medium">{t(h)}</th>)}
                  </tr></thead>
                  <tbody className="divide-y divide-line">
                    {ot.data.rows.map((r: any) => (
                      <tr key={r.employee}>
                        <td className="px-2 py-2 font-medium">{r.employee_name}</td>
                        <td className="px-2 py-2">{r.department ?? '—'}</td>
                        <td className="px-2 py-2 tabular-nums">{fmtNumber(r.hours, lang, 2)}</td>
                        <td className="px-2 py-2 tabular-nums">{r.days.length}</td>
                        <td className="px-2 py-2 tabular-nums">{r.monthly_wage ? fmtMoney(r.monthly_wage, lang) : '—'}</td>
                        <td className="px-2 py-2 tabular-nums">{r.monthly_basic ? fmtMoney(r.monthly_basic, lang) : '—'}</td>
                        <td className="px-2 py-2 tabular-nums font-semibold">{r.amount != null ? fmtMoney(r.amount, lang) : <span className="text-xs font-normal text-amber-800">{r.warning}</span>}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </Card>
        )
      )}
    </div>
  )
}
