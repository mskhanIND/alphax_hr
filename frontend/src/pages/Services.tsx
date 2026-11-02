import { useQuery } from '@tanstack/react-query'
import { Briefcase, CalendarDays, Clock, FileText, Folder, LogOut, Plane, Receipt, Star, Timer, Wallet } from 'lucide-react'
import { useState, type ReactNode } from 'react'
import { Link } from 'react-router-dom'
import { RequestForm, typeTitle } from '../components/RequestForm'
import { Card, PageHeader, Spinner } from '../components/ui'
import { api, type RequestType } from '../lib/api'
import { useI18n } from '../lib/i18n'

function Tile({ icon, label, hint, to, onClick }: { icon: ReactNode; label: string; hint?: string; to?: string; onClick?: () => void }) {
  const cls = 'flex min-h-24 flex-col items-start gap-2 rounded-2xl border border-line bg-white p-4 text-start transition hover:border-brand hover:shadow-sm active:scale-[0.99]'
  const body = <><span className="grid size-10 place-items-center rounded-xl bg-brand/10 text-brand">{icon}</span>
    <span className="text-sm font-medium leading-tight">{label}</span>{hint && <span className="text-xs text-muted">{hint}</span>}</>
  return to ? <Link to={to} className={cls}>{body}</Link> : <button type="button" onClick={onClick} className={cls}>{body}</button>
}

const CATEGORY_ORDER = ['Attendance', 'Letter', 'Finance', 'Government', 'Document', 'Travel', 'Asset', 'Separation', 'Other']
const CATEGORY_ICON: Record<string, ReactNode> = {
  Attendance: <Timer className="size-5" />, Letter: <FileText className="size-5" />, Finance: <Wallet className="size-5" />,
  Government: <Plane className="size-5" />, Document: <Folder className="size-5" />, Travel: <Briefcase className="size-5" />,
  Asset: <Briefcase className="size-5" />, Separation: <LogOut className="size-5" />, Other: <FileText className="size-5" />,
}

/** Every self-service in one place: the employee's "app home" for requests. */
export default function Services() {
  const { t, lang } = useI18n()
  const types = useQuery({ queryKey: ['request-types'], queryFn: () => api.requestTypes() })
  const [open, setOpen] = useState<string | null>(null)
  const groups: Record<string, RequestType[]> = {}
  for (const x of types.data ?? []) (groups[x.category] ??= []).push(x)
  return (
    <div className="flex flex-col gap-5">
      <PageHeader title={t('Services')} subtitle={t('Everything you can ask HR for, in one place')} />
      <Card title={t('Everyday')}>
        <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-6">
          <Tile icon={<CalendarDays className="size-5" />} label={t('Apply for leave')} to="/me/leave" />
          <Tile icon={<Clock className="size-5" />} label={t('Attendance & corrections')} to="/me/attendance" />
          <Tile icon={<Receipt className="size-5" />} label={t('Expense claim')} to="/me/expenses" />
          <Tile icon={<Wallet className="size-5" />} label={t('My Payslips')} to="/me/payslips" />
          <Tile icon={<Folder className="size-5" />} label={t('My documents')} to="/me/documents" />
          <Tile icon={<Star className="size-5" />} label={t('My performance')} to="/me/performance" />
        </div>
      </Card>
      {types.isLoading ? <Spinner /> : CATEGORY_ORDER.filter((c) => groups[c]?.length).map((c) => (
        <Card key={c} title={t(c)}>
          <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-6">
            {groups[c].map((rt) => (
              <Tile key={rt.name} icon={CATEGORY_ICON[c]} label={typeTitle(rt, lang)}
                hint={rt.non_saudi_only ? t('Non-Saudis') : undefined} onClick={() => setOpen(rt.name)} />
            ))}
          </div>
        </Card>
      ))}
      <p className="text-sm text-muted"><Link to="/me/requests" className="text-brand underline">{t('Track my requests')}</Link></p>
      <RequestForm open={!!open} initialType={open ?? undefined} onClose={() => setOpen(null)} />
    </div>
  )
}
