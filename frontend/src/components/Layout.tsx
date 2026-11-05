import clsx from 'clsx'
import { Fingerprint,
  BadgeCheck, CalendarDays, CalendarRange, Clock, FileText, Home, Landmark, LogOut, Menu, Scale, ShieldCheck, User, Users, Wallet, X, Settings2, CalendarClock, History, Network, CalendarCheck, Activity, ChevronDown, Inbox, Gavel, ShieldAlert, Receipt, Star, ArrowRightLeft, LayoutGrid, Folder, Download, Megaphone, MapPin, LocateFixed, LifeBuoy, BookOpen, BellRing, Hourglass, HandCoins, BadgePercent, BookOpenCheck } from 'lucide-react'
import { useState, type ReactNode } from 'react'
import { NavLink, Link, useLocation } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import { api, signOut } from '../lib/api'
import { useI18n } from '../lib/i18n'
import { useSession } from '../lib/session'
import { useInstall } from '../lib/pwa'
import { Avatar } from './ui'
import NotificationBell from './NotificationBell'

interface NavItem { to: string; label: string; icon: ReactNode; badge?: number }

export function useNav(): { group: string; items: NavItem[] }[] {
  const { t } = useI18n()
  const s = useSession()
  const inbox = useQuery({ queryKey: ['inbox'], queryFn: api.inbox, enabled: s.persona.approver || s.persona.hr, refetchInterval: 120_000 })
  const groups: { group: string; items: NavItem[] }[] = [{ group: '', items: [{ to: '/', label: t('Home'), icon: <Home className="size-5" /> }] }]
  if (s.persona.employee) {
    groups.push({
      group: t('Self service'),
      items: [
        { to: '/me/services', label: t('Services'), icon: <LayoutGrid className="size-5" /> },
        { to: '/me/requests', label: t('My Requests'), icon: <Inbox className="size-5" /> },
        { to: '/me/help', label: t('Help centre'), icon: <LifeBuoy className="size-5" /> },
        { to: '/me/leave', label: t('My Leave'), icon: <CalendarDays className="size-5" /> },
        { to: '/me/vacation-plan', label: t('Vacation plan'), icon: <CalendarRange className="size-5" /> },
        { to: '/me/attendance', label: t('My Attendance'), icon: <Clock className="size-5" /> },
      ],
    })
    groups.push({
      group: t('My pay'),
      items: [
        { to: '/me/payslips', label: t('My Payslips'), icon: <Wallet className="size-5" /> },
        { to: '/me/loans', label: t('My loans'), icon: <HandCoins className="size-5" /> },
        { to: '/me/expenses', label: t('My expenses'), icon: <Receipt className="size-5" /> },
      ],
    })
    groups.push({
      group: t('My file'),
      items: [
        { to: '/me/profile', label: t('My Profile'), icon: <User className="size-5" /> },
        { to: '/me/documents', label: t('My documents'), icon: <Folder className="size-5" /> },
        { to: '/me/performance', label: t('My performance'), icon: <Star className="size-5" /> },
        { to: '/me/warnings', label: t('My warnings'), icon: <ShieldAlert className="size-5" /> },
      ],
    })
  }
  if (s.persona.approver || s.persona.hr)
    groups.push({
      group: t('Manager'),
      items: [
        { to: '/approvals', label: t('Approvals'), icon: <BadgeCheck className="size-5" />, badge: (inbox.data as any)?.total },
        { to: '/approval-delays', label: t('Approval delays'), icon: <Hourglass className="size-5" /> },
        { to: '/my-team', label: t('My team'), icon: <Users className="size-5" /> },
        ...(s.persona.manager || s.persona.hr ? [{ to: '/team-appraisals', label: t('Team appraisals'), icon: <Star className="size-5" /> }] : []),
        ...(!s.persona.hr ? [{ to: '/checkins', label: t('Check-ins & movements'), icon: <MapPin className="size-5" /> }] : []),
        { to: '/vacation-planner', label: t('Vacation planner'), icon: <CalendarRange className="size-5" /> },
        { to: '/team', label: t('Team Calendar'), icon: <CalendarRange className="size-5" /> },
      ],
    })
  if (s.persona.hr) {
    groups.push({
      group: t('People'),
      items: [
        { to: '/people', label: t('Employees'), icon: <Users className="size-5" /> },
        { to: '/people?view=org', label: t('Org chart'), icon: <Network className="size-5" /> },
        { to: '/people/bulk-update', label: t('Bulk update'), icon: <Users className="size-5" /> },
        { to: '/announcements', label: t('Announcements'), icon: <Megaphone className="size-5" /> },
        { to: '/knowledge', label: t('Help centre articles'), icon: <BookOpen className="size-5" /> },
        { to: '/requests', label: t('Requests'), icon: <Inbox className="size-5" /> },
        { to: '/penalties', label: t('Warnings & penalties'), icon: <Gavel className="size-5" /> },
        { to: '/appraisals', label: t('Appraisals'), icon: <Star className="size-5" /> },
        { to: '/compliance', label: t('Compliance'), icon: <ShieldCheck className="size-5" /> },
      ],
    })
    groups.push({
      group: t('Time & attendance'),
      items: [
        { to: '/roster', label: t('Roster'), icon: <CalendarClock className="size-5" /> },
        { to: '/attendance', label: t('Attendance'), icon: <Clock className="size-5" /> },
        { to: '/checkins', label: t('Check-ins & movements'), icon: <MapPin className="size-5" /> },
        { to: '/work-locations', label: t('Work locations'), icon: <LocateFixed className="size-5" /> },
        { to: '/attendance-devices', label: t('Attendance devices'), icon: <Fingerprint className="size-5" /> },
        { to: '/attendance-policies', label: t('Attendance exceptions'), icon: <ShieldCheck className="size-5" /> },
      ],
    })
    groups.push({
      group: t('Leave'),
      items: [
        { to: '/leave-balances', label: t('Leave balances'), icon: <CalendarCheck className="size-5" /> },
      ],
    })
    groups.push({
      group: t('Payroll'),
      items: [
        { to: '/payroll', label: t('Payroll control centre'), icon: <Landmark className="size-5" /> },
        { to: '/payroll/loans', label: t('Loans & advances'), icon: <HandCoins className="size-5" /> },
        { to: '/payroll/adjustments', label: t('Bonuses & deductions'), icon: <BadgePercent className="size-5" /> },
        { to: '/payroll/accruals', label: t('Accruals'), icon: <BookOpenCheck className="size-5" /> },
        { to: '/payroll/settlements', label: t('Final settlements'), icon: <Receipt className="size-5" /> },
        { to: '/payroll/gosi', label: t('GOSI Register'), icon: <FileText className="size-5" /> },
        { to: '/payroll/eosb', label: t('End of Service'), icon: <Scale className="size-5" /> },
      ],
    })
    groups.push({
      group: t('Administration'),
      items: [
        ...(s.persona.hr_manager || s.persona.system_manager
          ? [{ to: '/setup', label: t('HR status & setup'), icon: <Activity className="size-5" /> }] : []),
        { to: '/leave-setup', label: t('Leave setup'), icon: <Settings2 className="size-5" /> },
        { to: '/notifications-setup', label: t('Notifications'), icon: <BellRing className="size-5" /> },
        ...(s.persona.hr_manager ? [{ to: '/cutover', label: t('Cut-over readiness'), icon: <ArrowRightLeft className="size-5" /> }] : []),
        { to: '/activity', label: t('Activity log'), icon: <History className="size-5" /> },
      ],
    })
  }
  const hidden = s.hidden_pages ?? []
  return groups
    .map((g) => ({ ...g, items: g.items.filter((i) => !hidden.includes(i.to.split('?')[0])) }))
    .filter((g) => g.items.length)
}

const NAV_KEY = 'alphax-nav-collapsed'

function NavList({ onNavigate }: { onNavigate?: () => void }) {
  const groups = useNav()
  const loc = useLocation()
  // Items that differ only by query (?view=org) need their own active test.
  const activeFor = (to: string, isActive: boolean) => {
    const [path, query] = to.split('?')
    if (query) return loc.pathname === path && loc.search.includes(query)
    if (path === '/people') return isActive && !loc.search.includes('view=org')
    return isActive
  }
  const [closed, setClosed] = useState<Set<string>>(() => {
    try { return new Set(JSON.parse(localStorage.getItem(NAV_KEY) ?? '[]')) } catch { return new Set() }
  })
  const toggle = (g: string) => {
    const n = new Set(closed)
    if (n.has(g)) n.delete(g); else n.add(g)
    setClosed(n)
    try { localStorage.setItem(NAV_KEY, JSON.stringify([...n])) } catch { /* storage blocked */ }
  }
  return (
    <nav className="flex flex-col gap-4">
      {groups.map((g) => (
        <div key={g.group || 'root'}>
          {g.group && (
            <button type="button" onClick={() => toggle(g.group)} aria-expanded={!closed.has(g.group)}
              className="mb-1 flex w-full items-center justify-between px-3 text-xs font-semibold uppercase tracking-wider text-white/50 hover:text-white/80">
              {g.group}<ChevronDown className={clsx('size-3.5 transition', closed.has(g.group) && '-rotate-90 rtl:rotate-90')} />
            </button>
          )}
          {!closed.has(g.group) && <ul className="flex flex-col gap-0.5">
            {g.items.map((item) => (
              <li key={item.to}>
                <NavLink
                  to={item.to}
                  end={item.to === '/' || item.to === '/payroll'}
                  onClick={onNavigate}
                  className={({ isActive }) =>
                    clsx('flex items-center gap-3 rounded-xl px-3 py-2 text-sm transition',
                      activeFor(item.to, isActive) ? 'bg-white/15 font-medium text-white' : 'text-white/75 hover:bg-white/10 hover:text-white')
                  }
                >
                  {item.icon}
                  <span className="flex-1">{item.label}</span>
                  {!!item.badge && <span className="rounded-full bg-gold px-2 text-xs font-semibold text-brand-700">{item.badge}</span>}
                </NavLink>
              </li>
            ))}
          </ul>}
        </div>
      ))}
    </nav>
  )
}

function Brand() {
  const s = useSession()
  return (
    <Link to="/" className="flex items-center gap-2 px-3">
      <img src={s.brand?.logo || import.meta.env.BASE_URL + 'logo.svg'} alt="" className={s.brand?.custom ? 'h-9 max-w-[7rem] rounded bg-white/95 object-contain p-0.5' : 'size-9'} data-testid="brand-logo" />
      <div className="min-w-0 leading-tight">
        <div className="truncate font-semibold text-white">{s.brand?.title || s.title}</div>
        <div className="truncate text-[11px] text-white/60">{s.brand?.tagline || 'Frappe HRMS · ERPNext'}</div>
      </div>
    </Link>
  )
}

/** Phone tab bar: the employee's daily destinations, thumb-reachable. */
function TabBar() {
  const { t } = useI18n()
  const s = useSession()
  const inbox = useQuery({ queryKey: ['inbox'], queryFn: api.inbox, enabled: s.persona.approver || s.persona.hr, refetchInterval: 120_000 })
  const tabs = [
    { to: '/', label: t('Home'), icon: <Home className="size-5" /> },
    ...(s.persona.employee ? [
      { to: '/me/services', label: t('Services'), icon: <LayoutGrid className="size-5" /> },
      { to: '/me/leave', label: t('Leave'), icon: <CalendarDays className="size-5" /> },
      { to: '/me/attendance', label: t('Attendance'), icon: <Clock className="size-5" /> },
    ] : []),
    ...(s.persona.approver || s.persona.hr
      ? [{ to: '/approvals', label: t('Approvals'), icon: <BadgeCheck className="size-5" />, badge: (inbox.data as any)?.total }]
      : s.persona.employee ? [{ to: '/me/profile', label: t('Profile'), icon: <User className="size-5" /> }] : []),
  ].filter((tab) => !(s.hidden_pages ?? []).includes(tab.to))
  if (tabs.length < 3) return null
  return (
    <nav className="fixed inset-x-0 bottom-0 z-30 border-t border-line bg-white/95 pb-[env(safe-area-inset-bottom)] backdrop-blur print:hidden lg:hidden" aria-label={t('Main')}>
      <ul className="grid" style={{ gridTemplateColumns: `repeat(${tabs.length}, minmax(0, 1fr))` }}>
        {tabs.map((tab) => (
          <li key={tab.to}>
            <NavLink to={tab.to} end={tab.to === '/'} className={({ isActive }) => clsx('relative flex flex-col items-center gap-0.5 py-2 text-[11px]', isActive ? 'font-semibold text-brand' : 'text-muted')}>
              {tab.icon}<span>{tab.label}</span>
              {!!(tab as any).badge && <span className="absolute top-1 ms-6 rounded-full bg-gold px-1.5 text-[10px] font-semibold text-brand-700">{(tab as any).badge}</span>}
            </NavLink>
          </li>
        ))}
      </ul>
    </nav>
  )
}

function InstallButton() {
  const { t } = useI18n()
  const { canPrompt, install } = useInstall()
  if (!canPrompt) return null
  return <button onClick={install} className="flex items-center gap-1.5 rounded-lg bg-brand px-3 py-1.5 text-sm font-medium text-white"><Download className="size-4" />{t('Install app')}</button>
}

export function Layout({ children }: { children: ReactNode }) {
  const { t, lang, setLang } = useI18n()
  const s = useSession()
  const [open, setOpen] = useState(false)
  return (
    <div className="flex min-h-full">
      <aside className="sticky top-0 hidden h-screen print:!hidden w-64 shrink-0 flex-col gap-6 overflow-y-auto bg-brand px-3 py-5 lg:flex">
        <Brand />
        <NavList />
      </aside>
      {open && (
        <div className="fixed inset-0 z-40 lg:hidden" onClick={() => setOpen(false)}>
          <div className="absolute inset-0 bg-slate-900/40" />
          <aside className="absolute inset-y-0 start-0 flex w-72 flex-col gap-6 overflow-y-auto bg-brand px-3 py-5" onClick={(e) => e.stopPropagation()}>
            <div className="flex items-center justify-between"><Brand /><button className="p-2 text-white" onClick={() => setOpen(false)} aria-label="Close menu"><X /></button></div>
            <NavList onNavigate={() => setOpen(false)} />
          </aside>
        </div>
      )}
      <div className="flex min-w-0 flex-1 flex-col">
        <header className="sticky top-0 z-30 flex h-16 print:hidden items-center gap-3 border-b border-line bg-white/90 px-4 backdrop-blur sm:px-6">
          <button className="rounded-lg p-2 hover:bg-surface lg:hidden" onClick={() => setOpen(true)} aria-label="Open menu"><Menu /></button>
          <div className="flex-1" />
          <InstallButton />
          <NotificationBell />
          {s.desk && <a href="/app" className="hidden rounded-lg border border-line px-3 py-1.5 text-sm font-medium hover:bg-surface sm:inline-block" title={t('Open the desk')}>{t('Desk')}</a>}
          <button
            onClick={() => setLang(lang === 'ar' ? 'en' : 'ar')}
            className="rounded-lg border border-line px-3 py-1.5 text-sm font-medium hover:bg-surface"
            aria-label={t('Language')}
          >
            {lang === 'ar' ? 'English' : 'العربية'}
          </button>
          <Link to={s.persona.employee ? '/me/profile' : '/'} className="flex items-center gap-2 rounded-xl p-1 pe-2 hover:bg-surface" title={t('My Profile')}>
            <Avatar name={s.full_name} image={s.user_image} size={34} />
            <div className="hidden text-sm leading-tight sm:block">
              <div className="font-medium">{s.full_name}</div>
              <div className="text-xs text-muted">{s.employee?.designation ?? s.user}</div>
            </div>
          </Link>
          <button type="button" onClick={signOut} className="rounded-lg p-2 text-muted hover:bg-surface" title={t('Sign out')} aria-label={t('Sign out')}>
            <LogOut className="size-5 flip-rtl" />
          </button>
        </header>
        <main className="mx-auto w-full max-w-7xl flex-1 px-4 pt-6 pb-24 sm:px-6 lg:pb-6">{children}</main>
      </div>
      <TabBar />
    </div>
  )
}
