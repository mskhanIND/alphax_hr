import { useQuery } from '@tanstack/react-query'
import clsx from 'clsx'
import { MapPin, Users } from 'lucide-react'
import { useState } from 'react'
import { Avatar, Badge, Card, Empty, ErrorBox, Input, PageHeader, Select, Spinner, Stat } from '../components/ui'
import { api } from '../lib/api'
import { fmtTime, todayISO } from '../lib/format'
import { useI18n } from '../lib/i18n'

const STATE: Record<string, { label: string; tone: string }> = {
  in: { label: 'Checked in', tone: 'green' }, out: { label: 'Checked out', tone: 'gray' },
  on_leave: { label: 'On leave', tone: 'blue' }, not_in: { label: 'Not checked in', tone: 'amber' },
}

/** Live check-ins and movements: who is in, where they punched, punches outside work locations. */
export default function Checkins() {
  const { t } = useI18n()
  const [date, setDate] = useState(todayISO())
  const [dept, setDept] = useState('')
  const [filter, setFilter] = useState<'all' | 'outside' | 'not_in'>('all')
  const q = useQuery({ queryKey: ['live-checkins', date, dept], queryFn: () => api.liveCheckins(date, dept || undefined), refetchInterval: 60_000 })
  const d = q.data
  const rows = (d?.rows ?? []).filter((r: any) => filter === 'all' || (filter === 'outside' ? r.outside > 0 : r.state === 'not_in'))
  return (
    <div className="flex flex-col gap-5">
      <PageHeader title={t('Check-ins & movements')} subtitle={t('Who is in, where they checked in, and punches outside work locations')}
        actions={<div className="flex flex-wrap gap-2">
          <Input type="date" className="w-40" value={date} max={todayISO()} onChange={(e) => e.target.value && setDate(e.target.value)} />
          {(d?.departments?.length ?? 0) > 1 && <Select className="w-48" value={dept} onChange={(e) => setDept(e.target.value)}>
            <option value="">{t('All departments')}</option>{d.departments.map((x: string) => <option key={x} value={x}>{x}</option>)}</Select>}
        </div>} />
      {q.isLoading ? <Spinner /> : q.error ? <ErrorBox error={q.error} onRetry={() => q.refetch()} /> : d && (
        <>
          <div className="grid grid-cols-2 gap-3 lg:grid-cols-5">
            <Stat label={t('Checked in')} value={d.summary.in} tone="brand" />
            <Stat label={t('Checked out')} value={d.summary.out} />
            <Stat label={t('Not checked in')} value={d.summary.not_in} tone="amber" />
            <Stat label={t('On leave')} value={d.summary.on_leave} tone="blue" />
            <Stat label={t('Outside a work location')} value={d.summary.outside} tone="red" />
          </div>
          <div className="flex gap-2">
            {(['all', 'outside', 'not_in'] as const).map((f) => (
              <button key={f} onClick={() => setFilter(f)} className={clsx('rounded-lg px-3 py-1.5 text-sm', filter === f ? 'bg-brand text-white' : 'border border-line bg-white')}>
                {t(f === 'all' ? 'All' : f === 'outside' ? 'Outside a work location' : 'Not checked in')}</button>
            ))}
          </div>
          <Card>
            {!rows.length ? <Empty title={t('Nobody here')} icon={<Users />} /> : (
              <ul className="divide-y divide-line">
                {rows.map((r: any) => (
                  <li key={r.name} className="flex flex-wrap items-center gap-3 py-3">
                    <Avatar name={r.employee_name} image={r.image} size={36} />
                    <div className="min-w-40 flex-1">
                      <div className="font-medium">{r.employee_name}</div>
                      <div className="text-xs text-muted">{r.department}{r.leave_type ? ` · ${r.leave_type}` : ''}</div>
                    </div>
                    <div className="flex flex-wrap gap-1.5">
                      {r.punches.map((p: any, i: number) => (
                        <a key={i} target="_blank" rel="noreferrer" href={p.latitude ? `https://www.google.com/maps?q=${p.latitude},${p.longitude}` : undefined}
                          className={clsx('inline-flex items-center gap-1 rounded-md px-2 py-0.5 text-xs tabular-nums', p.alphax_outside ? 'bg-red-50 text-red-700' : 'bg-surface text-muted', p.latitude && 'hover:underline')}
                          title={p.alphax_location ? `${p.alphax_location} · ${p.alphax_distance_m} m` : p.latitude ? t('Open on map') : t('No location')}>
                          {p.log_type} {fmtTime(p.time)}{p.latitude ? <MapPin className="size-3" /> : null}{p.alphax_outside ? ` ${p.alphax_distance_m} m` : ''}
                        </a>
                      ))}
                    </div>
                    <Badge tone={STATE[r.state].tone}>{t(STATE[r.state].label)}</Badge>
                  </li>
                ))}
              </ul>
            )}
          </Card>
        </>
      )}
    </div>
  )
}
