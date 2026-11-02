import { useQuery } from '@tanstack/react-query'
import clsx from 'clsx'
import { AlertTriangle, CheckCircle2, ChevronDown } from 'lucide-react'
import { useState } from 'react'
import { Link } from 'react-router-dom'
import { Badge, Card, ErrorBox, PageHeader, Spinner, Stat } from '../components/ui'
import { api } from '../lib/api'
import { fmtDate, fmtNumber } from '../lib/format'
import { useI18n } from '../lib/i18n'

const BUCKETS = ['expired', 'within_30', 'within_60', 'within_90', 'valid', 'missing'] as const
const BUCKET_COLOR: Record<string, string> = {
  expired: 'bg-red-500', within_30: 'bg-orange-500', within_60: 'bg-amber-400', within_90: 'bg-yellow-300', valid: 'bg-emerald-500', missing: 'bg-slate-300',
}

function Gauge({ value, target }: { value: number; target?: number | null }) {
  const r = 52, c = 2 * Math.PI * r
  const pct = Math.max(0, Math.min(100, value))
  return (
    <svg viewBox="0 0 120 120" className="size-36" role="img" aria-label={`${pct}%`}>
      <circle cx="60" cy="60" r={r} fill="none" stroke="var(--color-line)" strokeWidth="12" />
      <circle cx="60" cy="60" r={r} fill="none" stroke="var(--color-brand)" strokeWidth="12" strokeLinecap="round"
        strokeDasharray={`${(c * pct) / 100} ${c}`} transform="rotate(-90 60 60)" />
      {target ? <line x1="60" y1="2" x2="60" y2="16" stroke="var(--color-gold)" strokeWidth="3" transform={`rotate(${(360 * target) / 100} 60 60)`} /> : null}
      <text x="60" y="66" textAnchor="middle" className="fill-[var(--color-ink)] text-[20px] font-semibold">{pct.toFixed(1)}%</text>
    </svg>
  )
}

export default function Compliance() {
  const { t, lang } = useI18n()
  const q = useQuery<any>({ queryKey: ['compliance'], queryFn: api.compliance })
  const exp = useQuery<any[]>({ queryKey: ['expiring', 90], queryFn: () => api.expiring(90) })
  const [open, setOpen] = useState<string | null>(null)
  if (q.isLoading) return <Spinner />
  if (q.error) return <ErrorBox error={q.error} onRetry={() => q.refetch()} />
  const d = q.data
  const n = d.nitaqat
  return (
    <div className="flex flex-col gap-5">
      <PageHeader title={t('Compliance')} subtitle={`${d.company ?? ''} · ${fmtDate(d.as_of, lang)}`} />
      {d.company_holiday_list_outdated && (
        <div className="flex items-center gap-2 rounded-xl border border-amber-200 bg-amber-50 p-3 text-sm text-amber-900"><AlertTriangle className="size-4" />{t('Company holiday list is outdated')}: {d.company_holiday_list}</div>
      )}
      <div className="grid gap-5 lg:grid-cols-3">
        <Card title={t('Saudization (estimate)')}>
          <div className="flex items-center gap-4">
            <Gauge value={n.saudization_percent} target={n.target_percent} />
            <dl className="flex-1 space-y-1 text-sm">
              <div className="flex justify-between"><dt className="text-muted">{t('Headcount')}</dt><dd className="font-medium tabular-nums">{fmtNumber(n.total_employees, lang)}</dd></div>
              <div className="flex justify-between"><dt className="text-muted">{t('Saudis')}</dt><dd className="font-medium tabular-nums">{fmtNumber(n.saudi_headcount, lang)}</dd></div>
              <div className="flex justify-between"><dt className="text-muted">{t('Weighted Saudis')}</dt><dd className="font-medium tabular-nums">{fmtNumber(n.saudi_weighted, lang, 1)}</dd></div>
              {n.target_percent != null && <div className="flex justify-between"><dt className="text-muted">{t('Target')}</dt><dd className="font-medium tabular-nums">{n.target_percent}%</dd></div>}
              {n.saudis_needed_for_target != null && <div className="flex justify-between"><dt className="text-muted">{t('Saudis needed for target')}</dt><dd className="font-semibold tabular-nums text-brand">{fmtNumber(n.saudis_needed_for_target, lang)}</dd></div>}
            </dl>
          </div>
        </Card>
        <Card title={t('Document expiry')} className="lg:col-span-2">
          <div className="flex flex-col gap-3">
            {Object.entries(d.documents).map(([kind, counts]: [string, any]) => {
              const total = BUCKETS.reduce((s, b) => s + (counts[b] ?? 0), 0) || 1
              return (
                <div key={kind}>
                  <div className="mb-1 flex justify-between text-sm"><span className="font-medium">{t(kind === 'work_permit' ? 'Work permit' : kind.charAt(0).toUpperCase() + kind.slice(1))}</span>
                    <span className="text-muted">{t('expired')} {counts.expired} · {t('within_30')} {counts.within_30} · {t('missing')} {counts.missing}</span></div>
                  <div className="flex h-3 overflow-hidden rounded-full bg-surface">
                    {BUCKETS.map((b) => counts[b] ? <div key={b} title={`${t(b)}: ${counts[b]}`} className={BUCKET_COLOR[b]} style={{ width: `${(100 * counts[b]) / total}%` }} /> : null)}
                  </div>
                </div>
              )
            })}
            <div className="flex flex-wrap gap-3 pt-1 text-xs text-muted">{BUCKETS.map((b) => <span key={b} className="flex items-center gap-1"><span className={clsx('size-2.5 rounded-full', BUCKET_COLOR[b])} />{t(b)}</span>)}</div>
          </div>
        </Card>
      </div>
      <Card title={t('Data readiness')} subtitle={t('Fix these so leave, payroll and compliance work correctly.')}>
        <ul className="divide-y divide-line">
          {d.checks.map((c: any) => (
            <li key={c.key}>
              <button className="flex w-full items-center gap-3 py-3 text-start" onClick={() => setOpen(open === c.key ? null : c.key)} disabled={!c.count}>
                {c.count ? <AlertTriangle className={clsx('size-5', c.severity === 'high' ? 'text-red-600' : 'text-amber-600')} /> : <CheckCircle2 className="size-5 text-emerald-600" />}
                <span className="flex-1 text-sm font-medium">{t(c.key)}</span>
                {c.count ? <Badge tone={c.severity === 'high' ? 'red' : 'amber'}>{fmtNumber(c.count, lang)}</Badge> : <Badge tone="green">0</Badge>}
                {c.count ? <ChevronDown className={clsx('size-4 text-muted transition', open === c.key && 'rotate-180')} /> : <span className="size-4" />}
              </button>
              {open === c.key && (
                <ul className="mb-3 ms-8 grid gap-1 text-sm sm:grid-cols-2">
                  {c.sample.map((s: any) => (
                    <li key={s.employee}>{c.key === 'hr_user_restricted_to_own_record' ? <span>{s.employee_name} <span className="text-muted">({s.employee})</span></span> :
                      <Link to={`/people/${encodeURIComponent(s.employee)}`} className="text-brand hover:underline">{s.employee_name}</Link>}
                      {s.department && <span className="text-muted"> · {s.department}</span>}</li>
                  ))}
                  {c.count > c.sample.length && <li className="text-muted">+{c.count - c.sample.length}</li>}
                </ul>
              )}
            </li>
          ))}
        </ul>
      </Card>
      <Card title={`${t('Document expiry')} · 90 ${t('days')}`}>
        {exp.isLoading ? <Spinner /> : !(exp.data ?? []).length ? <p className="text-sm text-muted">{t('All caught up')}</p> : (
          <div className="grid gap-2 sm:grid-cols-2 lg:grid-cols-3">
            {exp.data!.slice(0, 30).map((r) => (
              <Link key={r.employee + r.document} to={`/people/${encodeURIComponent(r.employee)}`} className="rounded-xl border border-line p-3 hover:bg-surface">
                <div className="flex items-center justify-between"><span className="font-medium">{r.employee_name}</span>
                  <Badge tone={r.days_left < 0 ? 'red' : r.days_left <= 30 ? 'amber' : 'blue'}>{r.days_left < 0 ? t('expired') : `${r.days_left} ${t('days')}`}</Badge></div>
                <div className="text-sm text-muted">{t(r.document === 'work_permit' ? 'Work permit' : r.document.charAt(0).toUpperCase() + r.document.slice(1))} · {fmtDate(r.expiry, lang)}</div>
              </Link>
            ))}
          </div>
        )}
      </Card>
      <div className="grid grid-cols-2 gap-3 lg:hidden"><Stat label={t('Headcount')} value={fmtNumber(d.headcount, lang)} /></div>
    </div>
  )
}
