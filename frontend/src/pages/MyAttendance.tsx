import { useQuery } from '@tanstack/react-query'
import clsx from 'clsx'
import { ChevronLeft, ChevronRight } from 'lucide-react'
import { useEffect, useState } from 'react'
import { AttendanceRequests } from '../components/AttendanceRequests'
import { CheckInCard } from '../components/CheckInCard'
import { Button, Card, ErrorBox, PageHeader, Spinner, Stat } from '../components/ui'
import { api } from '../lib/api'
import { daysInMonth, fmtDate, fmtMonth, fmtNumber, monthStart, shiftMonth, todayISO } from '../lib/format'
import { useI18n } from '../lib/i18n'

function MyPolicy() {
  const { t } = useI18n()
  const q = useQuery({ queryKey: ['my-attendance-policy'], queryFn: api.myAttendancePolicy, staleTime: 300_000 })
  const p = q.data
  if (!p) return null
  const items = [
    p.exempt && t('You are exempt from attendance tracking.'),
    p.late_grace_minutes && `${t('Late grace')}: ${p.late_grace_minutes} ${t('min')}`,
    p.monthly_late_allowance > 0 && `${p.monthly_late_allowance} ${t('free late minutes / month')}`,
    p.single_punch_ok && t('Single punch OK'),
    p.permissions_per_month && `${p.permissions_per_month} ${t('permissions / month')}`,
  ].filter(Boolean)
  if (!items.length) return null
  return <p className="rounded-xl bg-brand/5 px-3 py-2 text-sm text-brand">{t('Your attendance rules')}: {items.join(' · ')}</p>
}

const COLORS: Record<string, string> = {
  Present: 'bg-emerald-500 text-white',
  Absent: 'bg-red-500 text-white',
  'On Leave': 'bg-sky-500 text-white',
  'Half Day': 'bg-amber-400 text-ink',
  'Work From Home': 'bg-violet-500 text-white',
}

export default function MyAttendance() {
  const { t, lang } = useI18n()
  const [month, setMonth] = useState(monthStart(todayISO()))
  const q = useQuery<any>({ queryKey: ['myAttendance', month], queryFn: () => api.myAttendance(month) })
  const [day, setDay] = useState(todayISO())
  useEffect(() => { if (day.slice(0, 7) !== month.slice(0, 7)) setDay(month.slice(0, 7) === todayISO().slice(0, 7) ? todayISO() : month) }, [month, day])
  const byDate: Record<string, any> = {}
  for (const r of q.data?.rows ?? []) byDate[r.attendance_date] = r
  const first = new Date(month + 'T00:00:00Z').getUTCDay() // 0 = Sunday
  const days = daysInMonth(month)
  const today = todayISO()
  const weekdays = lang === 'ar' ? ['أحد', 'إثنين', 'ثلاثاء', 'أربعاء', 'خميس', 'جمعة', 'سبت'] : ['Sun', 'Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat']
  return (
    <div className="flex flex-col gap-5">
      <PageHeader title={t('My Attendance')} />
      <CheckInCard />
      <MyPolicy />
      <AttendanceRequests />
      {q.error && <ErrorBox error={q.error} onRetry={() => q.refetch()} />}
      <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">
        <Stat label={t('Present')} value={fmtNumber(q.data?.summary?.Present ?? 0, lang)} />
        <Stat label={t('Absent')} value={fmtNumber(q.data?.summary?.Absent ?? 0, lang)} tone="red" />
        <Stat label={t('On Leave')} value={fmtNumber(q.data?.summary?.['On Leave'] ?? 0, lang)} tone="blue" />
        <Stat label={t('Late entries')} value={fmtNumber(q.data?.summary?.late ?? 0, lang)} tone="amber" />
      </div>
      <Card
        title={fmtMonth(month, lang)}
        action={
          <div className="flex gap-1">
            <Button variant="secondary" size="sm" onClick={() => setMonth(shiftMonth(month, -1))} aria-label={t('Previous')}><ChevronLeft className="size-4 flip-rtl" /></Button>
            <Button variant="secondary" size="sm" disabled={month >= monthStart(today)} onClick={() => setMonth(shiftMonth(month, 1))} aria-label={t('Next')}><ChevronRight className="size-4 flip-rtl" /></Button>
          </div>
        }
      >
        {q.isLoading ? <Spinner /> : (
          <div className="flex flex-col gap-5 md:flex-row md:items-start">
            <div className="w-full max-w-sm shrink-0">
              <div className="grid grid-cols-7 gap-1 text-center text-[11px] text-muted">{weekdays.map((d) => <div key={d}>{d}</div>)}</div>
              <div className="mt-1 grid grid-cols-7 gap-1">
                {Array.from({ length: first }).map((_, i) => <div key={'b' + i} />)}
                {Array.from({ length: days }).map((_, i) => {
                  const iso = month.slice(0, 8) + String(i + 1).padStart(2, '0')
                  const r = byDate[iso]
                  return (
                    <button type="button" key={iso} onClick={() => setDay(iso)}
                      title={r ? `${t(r.status)}${r.working_hours ? ` · ${r.working_hours.toFixed(1)}h` : ''}` : ''}
                      className={clsx('relative flex h-10 items-center justify-center rounded-lg text-sm tabular-nums transition',
                        r ? COLORS[r.status] ?? 'bg-slate-200' : 'bg-surface text-muted hover:bg-line',
                        iso === today && 'ring-2 ring-gold ring-offset-1', iso === day && 'outline outline-2 outline-brand')}>
                      {i + 1}
                      {r?.late_entry || r?.early_exit ? <span className="absolute bottom-0.5 size-1.5 rounded-full bg-amber-300" /> : null}
                    </button>
                  )
                })}
              </div>
            </div>
            <div className="flex min-w-0 flex-1 flex-col gap-4">
              {(() => {
                const r = byDate[day]
                return (
                  <div className="rounded-xl border border-line p-4">
                    <div className="text-sm text-muted">{fmtDate(day, lang)}</div>
                    {r ? (
                      <div className="mt-1 flex flex-col gap-1 text-sm">
                        <div className="text-base font-semibold">{t(r.status)}{r.leave_type ? ` · ${t(r.leave_type)}` : ''}</div>
                        {r.working_hours ? <div>{t('Working hours')}: {r.working_hours.toFixed(1)}</div> : null}
                        {r.shift && <div className="text-muted">{t('Shift')}: {r.shift}</div>}
                        {(r.late_entry || r.early_exit) && <div className="text-amber-700">{[r.late_entry ? t('Late entry') : null, r.early_exit ? t('Early exit') : null].filter(Boolean).join(' · ')}</div>}
                      </div>
                    ) : <div className="mt-1 text-sm text-muted">{day > today ? t('Not yet') : t('No attendance recorded for this day')}</div>}
                  </div>
                )
              })()}
              <div className="flex flex-wrap gap-3 text-xs text-muted">
                {Object.keys(COLORS).map((k) => <span key={k} className="flex items-center gap-1.5"><span className={clsx('size-3 rounded', COLORS[k])} />{t(k)}</span>)}
                <span className="flex items-center gap-1.5"><span className="size-2 rounded-full bg-amber-300" />{t('Late or early')}</span>
              </div>
            </div>
          </div>
        )}
      </Card>
    </div>
  )
}
