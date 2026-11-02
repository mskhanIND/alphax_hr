import clsx from 'clsx'
import {
  BadgeCheck, CalendarDays, CalendarRange, Clock, FileText, Home, Landmark, LogOut, Menu, Scale, ShieldCheck, User, Users, Wallet, X,
} from 'lucide-react'
import { useState, type ReactNode } from 'react'
import { NavLink, Link } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import { api } from '../lib/api'
import { useI18n } from '../lib/i18n'
import { useSession } from '../lib/session'
import { Avatar } from './ui'

interface NavItem { to: string; label: string; icon: ReactNode; badge?: number }

export function useNav(): { group: string; items: NavItem[] }[] {
  const { t } = useI18n()
  const s = useSession()
  const inbox = useQuery({ queryKey: ['inbox'], queryFn: api.inbox, enabled: s.persona.approver || s.persona.hr, refetchInterval: 120_000 })
  const groups: { group: string; items: NavItem[] }[] = [{ group: '', items: [{ to: '/', label: t('Home'), icon: <Home className="size-5" /> }] }]
  if (s.persona.employee)
    groups.push({
      group: t('My Space'),
      items: [
        { to: '/me/leave', label: t('My Leave'), icon: <CalendarDays className="size-5" /> },
        { to: '/me/attendance', label: t('My Attendance'), icon: <Clock className="size-5" /> },
        { to: '/me/payslips', label: t('My Payslips'), icon: <Wallet className="size-5" /> },
        { to: '/me/profile', label: t('My Profile'), icon: <User className="size-5" /> },
      ],
    })
  if (s.persona.approver || s.persona.hr)
    groups.push({
      group: t('Manager'),
      items: [
        { to: '/approvals', label: t('Approvals'), icon: <BadgeCheck className="size-5" />, badge: (inbox.data as any)?.total },
        { to: '/team', label: t('Team Calendar'), icon: <CalendarRange className="size-5" /> },
      ],
    })
  if (s.persona.hr)
    groups.push({
      group: t('HR Team'),
      items: [
        { to: '/people', label: t('People'), icon: <Users className="size-5" /> },
        { to: '/compliance', label: t('Compliance'), icon: <ShieldCheck className="size-5" /> },
        { to: '/payroll', label: t('Payroll'), icon: <Landmark className="size-5" /> },
        { to: '/payroll/gosi', label: t('GOSI Register'), icon: <FileText className="size-5" /> },
        { to: '/payroll/eosb', label: t('End of Service'), icon: <Scale className="size-5" /> },
      ],
    })
  return groups
}

function NavList({ onNavigate }: { onNavigate?: () => void }) {
  const groups = useNav()
  return (
    <nav className="flex flex-col gap-5">
      {groups.map((g) => (
        <div key={g.group || 'root'}>
          {g.group && <div className="mb-1 px-3 text-xs font-semibold uppercase tracking-wider text-white/50">{g.group}</div>}
          <ul className="flex flex-col gap-0.5">
            {g.items.map((item) => (
              <li key={item.to}>
                <NavLink
                  to={item.to}
                  end={item.to === '/' || item.to === '/payroll'}
                  onClick={onNavigate}
                  className={({ isActive }) =>
                    clsx('flex items-center gap-3 rounded-xl px-3 py-2 text-sm transition',
                      isActive ? 'bg-white/15 font-medium text-white' : 'text-white/75 hover:bg-white/10 hover:text-white')
                  }
                >
                  {item.icon}
                  <span className="flex-1">{item.label}</span>
                  {!!item.badge && <span className="rounded-full bg-gold px-2 text-xs font-semibold text-brand-700">{item.badge}</span>}
                </NavLink>
              </li>
            ))}
          </ul>
        </div>
      ))}
    </nav>
  )
}

function Brand() {
  const s = useSession()
  return (
    <Link to="/" className="flex items-center gap-2 px-3">
      <img src={import.meta.env.BASE_URL + 'logo.svg'} alt="" className="size-9" />
      <div className="leading-tight">
        <div className="font-semibold text-white">{s.title}</div>
        <div className="text-[11px] text-white/60">Frappe HRMS · ERPNext</div>
      </div>
    </Link>
  )
}

export function Layout({ children }: { children: ReactNode }) {
  const { t, lang, setLang } = useI18n()
  const s = useSession()
  const [open, setOpen] = useState(false)
  return (
    <div className="flex min-h-full">
      <aside className="sticky top-0 hidden h-screen w-64 shrink-0 flex-col gap-6 overflow-y-auto bg-brand px-3 py-5 lg:flex">
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
        <header className="sticky top-0 z-30 flex h-16 items-center gap-3 border-b border-line bg-white/90 px-4 backdrop-blur sm:px-6">
          <button className="rounded-lg p-2 hover:bg-surface lg:hidden" onClick={() => setOpen(true)} aria-label="Open menu"><Menu /></button>
          <div className="flex-1" />
          <button
            onClick={() => setLang(lang === 'ar' ? 'en' : 'ar')}
            className="rounded-lg border border-line px-3 py-1.5 text-sm font-medium hover:bg-surface"
            aria-label={t('Language')}
          >
            {lang === 'ar' ? 'English' : 'العربية'}
          </button>
          <div className="flex items-center gap-2">
            <Avatar name={s.full_name} image={s.user_image} size={34} />
            <div className="hidden text-sm leading-tight sm:block">
              <div className="font-medium">{s.full_name}</div>
              <div className="text-xs text-muted">{s.employee?.designation ?? s.user}</div>
            </div>
          </div>
          <a href="/api/method/logout?redirect-to=/login" className="rounded-lg p-2 text-muted hover:bg-surface" title={t('Sign out')} aria-label={t('Sign out')}>
            <LogOut className="size-5 flip-rtl" />
          </a>
        </header>
        <main className="mx-auto w-full max-w-7xl flex-1 px-4 py-6 sm:px-6">{children}</main>
      </div>
    </div>
  )
}
