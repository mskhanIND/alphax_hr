import { useQuery } from '@tanstack/react-query'
import clsx from 'clsx'
import { ChevronLeft, ChevronRight } from 'lucide-react'
import { useState } from 'react'
import { AttendanceRequests } from '../components/AttendanceRequests'
import { CheckInCard } from '../components/CheckInCard'
import { Button, Card, ErrorBox, PageHeader, Spinner, Stat } from '../components/ui'
import { api } from '../lib/api'
import { daysInMonth, fmtMonth, fmtNumber, monthStart, shiftMonth, todayISO } from '../lib/format'
import { useI18n } from '../lib/i18n'

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
          <>
            <div className="grid grid-cols-7 gap-1.5 text-center text-xs text-muted">{weekdays.map((d) => <div key={d}>{d}</div>)}</div>
            <div className="mt-1.5 grid grid-cols-7 gap-1.5">
              {Array.from({ length: first }).map((_, i) => <div key={'b' + i} />)}
              {Array.from({ length: days }).map((_, i) => {
                const iso = month.slice(0, 8) + String(i + 1).padStart(2, '0')
                const r = byDate[iso]
                return (
                  <div
                    key={iso}
                    title={r ? `${t(r.status)}${r.working_hours ? ` · ${r.working_hours.toFixed(1)}h` : ''}` : ''}
                    className={clsx('flex aspect-square flex-col items-center justify-center rounded-xl text-sm tabular-nums',
                      r ? COLORS[r.status] ?? 'bg-slate-200' : 'bg-surface text-muted', iso === today && 'ring-2 ring-gold ring-offset-1')}
                  >
                    {i + 1}
                    {r?.late_entry ? <span className="text-[9px] leading-none">●</span> : null}
                  </div>
                )
              })}
            </div>
            <div className="mt-4 flex flex-wrap gap-3 text-xs text-muted">
              {Object.keys(COLORS).map((k) => <span key={k} className="flex items-center gap-1.5"><span className={clsx('size-3 rounded', COLORS[k])} />{t(k)}</span>)}
            </div>
          </>
        )}
      </Card>
    </div>
  )
}
