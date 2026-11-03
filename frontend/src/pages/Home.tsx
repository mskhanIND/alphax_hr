import { useQuery } from '@tanstack/react-query'
import { AlertTriangle, BadgeCheck, CalendarDays, Inbox, Megaphone, ShieldAlert, ChevronRight, LayoutGrid, Receipt, ShieldCheck, Smartphone, Users, Wallet, X } from 'lucide-react'
import { useState, type ReactNode } from 'react'
import { useInstall } from '../lib/pwa'
import { Link } from 'react-router-dom'
import { CheckInCard } from '../components/CheckInCard'
import { Badge, Card, Empty, ErrorBox, Modal, Spinner, Stat, StatusBadge } from '../components/ui'
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
        <Link to="/people" className="rounded-2xl transition hover:-translate-y-0.5 hover:shadow-md"><Stat label={t('Active employees')} value={fmtNumber(org.data?.active, lang)} icon={<Users className="size-4" />} /></Link>
        <Link to="/compliance" className="rounded-2xl transition hover:-translate-y-0.5 hover:shadow-md"><Stat label={t('Saudization (estimate)')} value={comp.data ? `${fmtNumber(comp.data.nitaqat.saudization_percent, lang, 1)}%` : '—'} icon={<ShieldCheck className="size-4" />} /></Link>
        <Link to="/people?view=table" className="rounded-2xl transition hover:-translate-y-0.5 hover:shadow-md"><Stat label={t('Joiners (30 days)')} value={fmtNumber(org.data?.joiners_30d, lang)} icon={<CalendarDays className="size-4" />} tone="blue" /></Link>
        <Link to="/compliance?open=documents" className="rounded-2xl transition hover:-translate-y-0.5 hover:shadow-md"><Stat label={t('Iqama') + ' · ' + t('within_30')} value={fmtNumber((comp.data?.documents?.iqama?.within_30 ?? 0) + (comp.data?.documents?.iqama?.expired ?? 0), lang)} icon={<AlertTriangle className="size-4" />} tone="amber" /></Link>
      </div>
      <Card title={t('Data readiness')} action={<Link to="/compliance" className="text-sm font-medium text-brand">{t('Open compliance')}</Link>} className="lg:row-span-2">
        {comp.isLoading ? <Spinner /> : comp.error ? <ErrorBox error={comp.error} onRetry={() => comp.refetch()} /> : issues.length === 0 ? <Empty title={t('All caught up')} /> : (
          <ul className="divide-y divide-line">
            {issues.slice(0, 6).map((c: any) => (
              <li key={c.key}>
                <Link to={`/compliance?open=${c.key}`} className="flex items-center justify-between gap-2 rounded-lg px-1 py-2 text-sm hover:bg-surface">
                  <span>{t(c.key)}</span>
                  <Badge tone={c.severity === 'high' ? 'red' : 'amber'}>{fmtNumber(c.count, lang)}</Badge>
                </Link>
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
              <Link key={d.department ?? 'none'} to={d.department ? `/people?view=table&department=${encodeURIComponent(d.department)}` : '/people'} className="block rounded-lg px-1 py-0.5 text-sm hover:bg-surface">
                <div className="flex justify-between"><span>{d.department ?? '—'}</span><span className="tabular-nums text-muted">{d.n}</span></div>
                <div className="mt-1 h-2 rounded-full bg-surface"><div className="h-2 rounded-full bg-brand" style={{ width: `${pct}%` }} /></div>
              </Link>
            )
          })}
        </div>
      </Card>
    </div>
  )
}

function InstallHint() {
  const { t } = useI18n()
  const { canPrompt, showIOSHint, install } = useInstall()
  const [hidden, setHidden] = useState(() => { try { return localStorage.getItem('alphax-install-hint') === 'off' } catch { return false } })
  if (hidden || (!canPrompt && !showIOSHint)) return null
  const close = () => { setHidden(true); try { localStorage.setItem('alphax-install-hint', 'off') } catch { /* blocked */ } }
  return (
    <div className="flex items-center gap-3 rounded-2xl border border-brand/20 bg-brand/5 p-3 text-sm lg:hidden">
      <Smartphone className="size-5 shrink-0 text-brand" />
      <div className="flex-1">{canPrompt ? t('Install AlphaX HR on your phone for one-tap check-in.') : t('Install on iPhone: tap Share, then “Add to Home Screen”.')}</div>
      {canPrompt && <button className="rounded-lg bg-brand px-3 py-1.5 font-medium text-white" onClick={install}>{t('Install')}</button>}
      <button className="p-1 text-muted" onClick={close} aria-label={t('Close')}><X className="size-4" /></button>
    </div>
  )
}

function QuickServices() {
  const { t } = useI18n()
  const items = [
    { to: '/me/services', label: t('Services'), icon: <LayoutGrid className="size-5" /> },
    { to: '/me/leave', label: t('Leave'), icon: <CalendarDays className="size-5" /> },
    { to: '/me/expenses', label: t('Expense claim'), icon: <Receipt className="size-5" /> },
    { to: '/me/payslips', label: t('Payslips'), icon: <Wallet className="size-5" /> },
  ]
  return (
    <div className="grid grid-cols-4 gap-2">
      {items.map((i) => (
        <Link key={i.to} to={i.to} className="flex flex-col items-center gap-1 rounded-2xl border border-line bg-white p-3 text-center text-xs font-medium hover:border-brand">
          <span className="grid size-10 place-items-center rounded-xl bg-brand/10 text-brand">{i.icon}</span>{i.label}
        </Link>
      ))}
    </div>
  )
}

function Announcements() {
  const { t, lang } = useI18n()
  const q = useQuery({ queryKey: ['announcements'], queryFn: api.announcements, staleTime: 120_000 })
  const [open, setOpen] = useState<any>(null)
  if (!q.data?.length) return null
  const title = (a: any) => (lang === 'ar' && a.title_ar) || a.title
  const body = (a: any) => (lang === 'ar' && a.body_ar) || a.body
  return (
    <Card title={t('Announcements')}>
      <ul className="divide-y divide-line">
        {q.data.slice(0, 4).map((a: any) => (
          <li key={a.name}>
            <button type="button" className="flex w-full items-start gap-3 py-2.5 text-start" onClick={() => setOpen(a)}>
              <Megaphone className={`mt-0.5 size-4 shrink-0 ${a.priority === 'Important' ? 'text-red-600' : 'text-brand'}`} />
              <span className="min-w-0 flex-1">
                <span className="block font-medium">{title(a)}{a.pinned ? ' 📌' : ''}</span>
                <span className="line-clamp-2 text-sm text-muted">{body(a)}</span>
              </span>
              <span className="shrink-0 text-xs text-muted">{fmtDate(a.publish_on, lang)}</span>
            </button>
          </li>
        ))}
      </ul>
      {open && (
        <Modal open onClose={() => setOpen(null)} title={title(open)}>
          <p className="mb-2 text-xs text-muted">{open.by} · {fmtDate(open.publish_on, lang)}</p>
          <p className="whitespace-pre-wrap text-sm">{body(open)}</p>
          {open.attachment && <a className="mt-3 inline-block text-sm font-medium text-brand underline" href={open.attachment} target="_blank" rel="noreferrer">{t('Attachment')}</a>}
        </Modal>
      )}
    </Card>
  )
}

const ACTIVITY_ICON: Record<string, ReactNode> = {
  leave: <CalendarDays className="size-4" />, request: <Inbox className="size-4" />, payslip: <Wallet className="size-4" />,
  expense: <Receipt className="size-4" />, warning: <ShieldAlert className="size-4" />,
}

function RecentActivity() {
  const { t, lang } = useI18n()
  const q = useQuery({ queryKey: ['my-activity'], queryFn: api.myActivity, staleTime: 60_000 })
  return (
    <Card title={t('Recent activity')}>
      {q.isLoading ? <Spinner /> : !q.data?.length ? <p className="text-sm text-muted">{t('Nothing in the last 60 days.')}</p> : (
        <ul className="divide-y divide-line">
          {q.data.slice(0, 8).map((a: any, i: number) => (
            <li key={i}>
              <Link to={a.link} className="flex items-center gap-3 py-2 text-sm hover:text-brand">
                <span className="grid size-8 shrink-0 place-items-center rounded-lg bg-brand/10 text-brand">{ACTIVITY_ICON[a.kind]}</span>
                <span className="min-w-0 flex-1 truncate">{a.title}</span>
                {a.status && <StatusBadge status={a.status} />}
                <span className="shrink-0 text-xs text-muted">{fmtDate(a.at, lang, { day: '2-digit', month: 'short' })}</span>
              </Link>
            </li>
          ))}
        </ul>
      )}
    </Card>
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
      <InstallHint />
      <Announcements />
      {s.persona.employee && <QuickServices />}
      {s.persona.employee && (
        <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
          <CheckInCard />
          <LeaveSummary />
          <div className="min-w-0 lg:col-span-2"><RecentActivity /></div>
        </div>
      )}
      {(s.persona.approver || s.persona.hr) && <ApprovalsSummary />}
      {s.persona.hr && <HRSummary />}
    </div>
  )
}
