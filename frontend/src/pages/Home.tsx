import { useQuery } from '@tanstack/react-query'
import { AlertTriangle, BadgeCheck, CalendarDays, ChevronRight, ShieldCheck, Users } from 'lucide-react'
import { Link } from 'react-router-dom'
import { CheckInCard } from '../components/CheckInCard'
import { Badge, Card, Empty, Spinner, Stat } from '../components/ui'
import { api } from '../lib/api'
import { fmtDate, fmtNumber } from '../lib/format'
import { useI18n } from '../lib/i18n'
import { useSession } from '../lib/session'

function greeting(t: (s: string) => string) {
  const h = Number(new Intl.DateTimeFormat('en-GB', { hour: 'numeric', hour12: false, timeZone: 'Asia/Riyadh' }).format(new Date()))
  return h < 12 ? t('Good morning') : h < 17 ? t('Good afternoon') : t('Good evening')
}

function LeaveSummary() {
  const { t, lang } = useI18n()
  const q = useQuery<any>({ queryKey: ['balances'], queryFn: api.balances })
  const hol = useQuery<any>({ queryKey: ['holidays'], queryFn: api.holidays })
  return (
    <Card title={t('Leave balance')} action={<Link to="/me/leave" className="text-sm font-medium text-brand">{t('Apply for leave')}</Link>}>
      {q.isLoading ? <Spinner /> : !(q.data?.balances ?? []).length ? <p className="text-sm text-muted">—</p> : (
        <ul className="divide-y divide-line">
          {(q.data?.balances ?? []).slice(0, 4).map((b: any) => (
            <li key={b.leave_type} className="flex items-center justify-between py-2 text-sm">
              <span>{b.leave_type}</span>
              <span className="font-semibold tabular-nums">{fmtNumber(b.balance, lang, 1)} <span className="font-normal text-muted">{t('days')}</span></span>
            </li>
          ))}
        </ul>
      )}
      <div className="mt-4 border-t border-line pt-3">
        <div className="mb-1 text-xs font-semibold uppercase text-muted">{t('Upcoming holidays')}</div>
        {(hol.data?.holidays ?? []).length === 0 ? <p className="text-sm text-muted">{t('No holidays in the next 60 days')}</p> :
          hol.data.holidays.slice(0, 3).map((h: any) => (
            <div key={h.holiday_date} className="flex justify-between py-1 text-sm"><span>{h.description}</span><span className="text-muted">{fmtDate(h.holiday_date, lang)}</span></div>
          ))}
      </div>
    </Card>
  )
}

function ApprovalsSummary() {
  const { t } = useI18n()
  const q = useQuery<any>({ queryKey: ['inbox'], queryFn: api.inbox })
  return (
    <Card title={t('Pending approvals')} action={<Link to="/approvals" className="text-sm font-medium text-brand">{t('Open inbox')}</Link>}>
      {q.isLoading ? <Spinner /> : q.data?.total ? (
        <ul className="divide-y divide-line">
          {q.data.items.slice(0, 5).map((r: any) => (
            <li key={r.doctype + r.name} className="flex items-center justify-between py-2 text-sm">
              <div><div className="font-medium">{r.employee_name ?? r.owner}</div><div className="text-xs text-muted">{t(r.doctype)}{r.leave_type ? ` · ${r.leave_type}` : ''}</div></div>
              <ChevronRight className="size-4 text-muted flip-rtl" />
            </li>
          ))}
        </ul>
      ) : <Empty title={t('All caught up')} icon={<BadgeCheck />}>{t('Nothing is waiting for you.')}</Empty>}
    </Card>
  )
}

function HRSummary() {
  const { t, lang } = useI18n()
  const org = useQuery<any>({ queryKey: ['org'], queryFn: api.orgSummary })
  const comp = useQuery<any>({ queryKey: ['compliance'], queryFn: api.compliance })
  const issues = (comp.data?.checks ?? []).filter((c: any) => c.count > 0)
  return (
    <div className="grid gap-4 lg:grid-cols-3">
      <div className="grid grid-cols-2 gap-4 lg:col-span-2 lg:grid-cols-4">
        <Stat label={t('Active employees')} value={fmtNumber(org.data?.active, lang)} icon={<Users className="size-4" />} />
        <Stat label={t('Saudization (estimate)')} value={comp.data ? `${fmtNumber(comp.data.nitaqat.saudization_percent, lang, 1)}%` : '—'} icon={<ShieldCheck className="size-4" />} />
        <Stat label={t('Joiners (30 days)')} value={fmtNumber(org.data?.joiners_30d, lang)} icon={<CalendarDays className="size-4" />} tone="blue" />
        <Stat label={t('Iqama') + ' · ' + t('within_30')} value={fmtNumber((comp.data?.documents?.iqama?.within_30 ?? 0) + (comp.data?.documents?.iqama?.expired ?? 0), lang)} icon={<AlertTriangle className="size-4" />} tone="amber" />
      </div>
      <Card title={t('Data readiness')} action={<Link to="/compliance" className="text-sm font-medium text-brand">{t('Open compliance')}</Link>} className="lg:row-span-2">
        {comp.isLoading ? <Spinner /> : issues.length === 0 ? <Empty title={t('All caught up')} /> : (
          <ul className="divide-y divide-line">
            {issues.slice(0, 6).map((c: any) => (
              <li key={c.key} className="flex items-center justify-between gap-2 py-2 text-sm">
                <span>{t(c.key)}</span>
                <Badge tone={c.severity === 'high' ? 'red' : 'amber'}>{fmtNumber(c.count, lang)}</Badge>
              </li>
            ))}
          </ul>
        )}
      </Card>
      <Card title={t('By department')} className="lg:col-span-2">
        <div className="flex flex-col gap-2">
          {(org.data?.by_department ?? []).slice(0, 8).map((d: any) => {
            const pct = org.data.active ? (100 * d.n) / org.data.active : 0
            return (
              <div key={d.department ?? 'none'} className="text-sm">
                <div className="flex justify-between"><span>{d.department ?? '—'}</span><span className="tabular-nums text-muted">{d.n}</span></div>
                <div className="mt-1 h-2 rounded-full bg-surface"><div className="h-2 rounded-full bg-brand" style={{ width: `${pct}%` }} /></div>
              </div>
            )
          })}
        </div>
      </Card>
    </div>
  )
}

export default function Home() {
  const { t, lang } = useI18n()
  const s = useSession()
  return (
    <div className="flex flex-col gap-5">
      <div>
        <p className="text-sm text-muted">{fmtDate(new Intl.DateTimeFormat('en-CA', { timeZone: 'Asia/Riyadh' }).format(new Date()), lang, { weekday: 'long', day: 'numeric', month: 'long', year: 'numeric' })}</p>
        <h1 className="text-2xl font-semibold tracking-tight">{greeting(t)}{lang === 'ar' ? '، ' : ', '}{s.full_name.split(' ')[0]}</h1>
      </div>
      {!s.persona.employee && !s.persona.hr && !s.persona.approver && (
        <Card><Empty title={t('Your user is not linked to an employee record.')} /></Card>
      )}
      {s.persona.employee && (
        <div className="grid gap-4 lg:grid-cols-2">
          <CheckInCard />
          <LeaveSummary />
        </div>
      )}
      {(s.persona.approver || s.persona.hr) && <ApprovalsSummary />}
      {s.persona.hr && <HRSummary />}
    </div>
  )
}
