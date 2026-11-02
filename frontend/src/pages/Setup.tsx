import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import clsx from 'clsx'
import { AlertTriangle, CheckCircle2, RefreshCw, XCircle } from 'lucide-react'
import { useEffect, useState } from 'react'
import { Link, useLocation } from 'react-router-dom'
import { FieldInput } from '../components/FieldInput'
import { LinkInput } from '../components/LinkInput'
import { Button, Card, ErrorBox, Field, PageHeader, Select, Spinner, Stat } from '../components/ui'
import { api } from '../lib/api'
import { useI18n } from '../lib/i18n'

const CHECK_LABEL: Record<string, string> = {
  scheduler: 'Scheduler', workers: 'Background workers', alphax_jobs: 'AlphaX scheduled jobs', alphax_job_failures: 'Failed AlphaX jobs (24h)',
  error_log_24h: 'Errors logged (24h)', outgoing_email: 'Outgoing email', employee_row_size: 'Employee table space',
  default_company: 'Default company', holiday_lists: 'Holiday lists', leave_approver: 'Leave approvers', shift_approver: 'Shift approvers',
  reports_to: 'Reporting managers', user_account: 'Employee user accounts', salary_mapping: 'Salary component mapping',
  annual_leave: 'Annual leave', statutory_leave: 'Statutory leave types', gosi_rates: 'GOSI rates', check_failed: 'Check could not run',
}
const ICON = {
  ok: <CheckCircle2 className="size-5 text-emerald-600" />,
  warn: <AlertTriangle className="size-5 text-amber-500" />,
  error: <XCircle className="size-5 text-red-600" />,
}

function Health() {
  const { t } = useI18n()
  const q = useQuery<any>({ queryKey: ['health'], queryFn: api.health })
  if (q.isLoading) return <Spinner />
  if (q.error) return <ErrorBox error={q.error} onRetry={() => q.refetch()} />
  const d = q.data
  const groups: string[] = [...new Set<string>(d.checks.map((c: any) => c.group))]
  return (
    <div className="flex flex-col gap-5">
      <div className="grid grid-cols-3 gap-3">
        <Stat label={t('Healthy')} value={d.counts.ok} />
        <Stat label={t('Warnings')} value={d.counts.warn} tone="amber" />
        <Stat label={t('Problems')} value={d.counts.error} tone="red" />
      </div>
      {groups.map((g) => (
        <Card key={g} title={t(g)} action={<Button size="sm" variant="ghost" loading={q.isFetching} onClick={() => q.refetch()}><RefreshCw className="size-4" />{t('Re-check')}</Button>}>
          <ul className="divide-y divide-line">
            {d.checks.filter((c: any) => c.group === g).sort((a: any, b: any) => ['error', 'warn', 'ok'].indexOf(a.status) - ['error', 'warn', 'ok'].indexOf(b.status)).map((c: any) => (
              <li key={c.key} className="flex items-start gap-3 py-3">
                {ICON[c.status as keyof typeof ICON]}
                <div className="min-w-0 flex-1">
                  <div className="flex flex-wrap items-baseline justify-between gap-2">
                    <span className="font-medium">{t(CHECK_LABEL[c.key] ?? c.key)}</span>
                    <span className={clsx('text-sm tabular-nums', c.status === 'ok' ? 'text-muted' : c.status === 'warn' ? 'text-amber-800' : 'text-red-700')}>{c.value ?? ''}</span>
                  </div>
                  {c.detail && <p className="mt-0.5 text-sm text-muted">{c.detail}</p>}
                </div>
                {c.link && c.status !== 'ok' && (c.link.startsWith('/app')
                  ? <a href={c.link} target="_blank" rel="noreferrer" className="shrink-0 text-sm font-medium text-brand hover:underline">{t('Open')}</a>
                  : <Link to={c.link} className="shrink-0 text-sm font-medium text-brand hover:underline">{t('Fix')}</Link>)}
              </li>
            ))}
          </ul>
        </Card>
      ))}
      <Card title={t('Installed apps')}>
        <div className="flex flex-wrap gap-2 text-sm">
          {Object.entries(d.versions).map(([app, v]) => <span key={app} className="rounded-lg bg-surface px-2 py-1"><b>{app}</b> {String(v)}</span>)}
        </div>
        <p className="mt-2 text-xs text-muted">{d.site} · {d.as_of.slice(0, 16)}</p>
      </Card>
    </div>
  )
}

function SettingsForm() {
  const { t } = useI18n()
  const qc = useQueryClient()
  const q = useQuery<any>({ queryKey: ['settings'], queryFn: api.getSettings })
  const [values, setValues] = useState<Record<string, any>>({})
  const [map, setMap] = useState<any[]>([])
  useEffect(() => { if (q.data) { setValues(q.data.values); setMap(q.data.component_map) } }, [q.data])
  const save = useMutation({ mutationFn: () => api.saveSettings({ values, component_map: map }), onSuccess: (d) => { qc.setQueryData(['settings'], d); qc.invalidateQueries({ queryKey: ['health'] }) } })
  if (q.isLoading) return <Spinner />
  if (q.error) return <ErrorBox error={q.error} onRetry={() => q.refetch()} />
  const can = q.data.can_edit
  return (
    <div className="flex flex-col gap-5">
      {q.data.sections.map((sec: any) => (
        <Card key={sec.key} title={sec.label}>
          <div className="grid gap-4 sm:grid-cols-2">
            {sec.fields.map((f: any) => (
              f.fieldtype === 'Check' ? (
                <label key={f.fieldname} className="flex items-start gap-2 text-sm sm:col-span-2">
                  <input type="checkbox" className="mt-0.5 size-4 accent-[var(--color-brand)]" disabled={!can} checked={!!Number(values[f.fieldname])}
                    onChange={(e) => setValues({ ...values, [f.fieldname]: e.target.checked ? 1 : 0 })} />
                  <span><span className="font-medium">{f.label}</span>{f.description && <span className="block text-xs text-muted">{f.description}</span>}</span>
                </label>
              ) : (
                <Field key={f.fieldname} label={f.label} hint={f.description ?? undefined}>
                  <fieldset disabled={!can}><FieldInput spec={f} value={values[f.fieldname]} onChange={(v) => setValues({ ...values, [f.fieldname]: v })} /></fieldset>
                </Field>
              )
            ))}
          </div>
          {sec.key === 'gosi_section' && (
            <div className="mt-5 border-t border-line pt-4">
              <div className="mb-1 text-sm font-medium">{t('Salary component mapping')}</div>
              <p className="mb-3 text-xs text-muted">{t('Tell AlphaX which salary components are GOSI Basic, GOSI Housing and the EOSB wage.')}</p>
              <div className="flex flex-col gap-2">
                {map.map((r, i) => (
                  <div key={i} className="grid grid-cols-[1fr_12rem_auto] gap-2">
                    <LinkInput doctype="Salary Component" value={r.salary_component} disabled={!can} onChange={(v) => setMap(map.map((x, j) => j === i ? { ...x, salary_component: v } : x))} />
                    <Select value={r.purpose} disabled={!can} onChange={(e) => setMap(map.map((x, j) => j === i ? { ...x, purpose: e.target.value } : x))}>
                      {(q.data.purposes ?? []).map((p: string) => <option key={p} value={p}>{t(p)}</option>)}
                    </Select>
                    {can && <Button variant="ghost" size="sm" onClick={() => setMap(map.filter((_, j) => j !== i))} aria-label={t('Remove')}>✕</Button>}
                  </div>
                ))}
                {can && <Button variant="secondary" size="sm" className="self-start" onClick={() => setMap([...map, { salary_component: '', purpose: 'GOSI Basic' }])}>{t('Add component')}</Button>}
              </div>
            </div>
          )}
        </Card>
      ))}
      <Card title={t('More setup')}>
        <div className="flex flex-wrap gap-2">
          <Link to="/leave-setup"><Button variant="secondary">{t('Leave setup')}</Button></Link>
          <Link to="/roster"><Button variant="secondary">{t('Roster & week-offs')}</Button></Link>
          <Link to="/compliance"><Button variant="secondary">{t('Data readiness')}</Button></Link>
          <a href="/app/gosi-contribution-rate" target="_blank" rel="noreferrer"><Button variant="secondary">{t('GOSI rates')}</Button></a>
          <a href="/app/holiday-list" target="_blank" rel="noreferrer"><Button variant="secondary">{t('Holiday lists')}</Button></a>
        </div>
      </Card>
      {save.error && <ErrorBox error={save.error} />}
      {can && <div className="sticky bottom-4"><Button loading={save.isPending} onClick={() => save.mutate()}>{t('Save settings')}</Button>{save.isSuccess && <span className="ms-3 text-sm text-emerald-700">{t('Saved')}</span>}</div>}
    </div>
  )
}

export default function Setup() {
  const { t } = useI18n()
  const loc = useLocation()
  const [tab, setTab] = useState<'health' | 'settings'>(loc.hash === '#settings' ? 'settings' : 'health')
  return (
    <div className="flex flex-col gap-5">
      <PageHeader title={t('Setup & health')} subtitle={t('Is the HR system healthy, and how is AlphaX set up — in one place.')}
        actions={<div className="flex rounded-xl border border-line p-0.5" role="tablist">
          {(['health', 'settings'] as const).map((v) => (
            <button key={v} role="tab" aria-selected={tab === v} onClick={() => setTab(v)}
              className={clsx('rounded-lg px-3 py-1.5 text-sm', tab === v ? 'bg-brand text-white' : 'text-muted hover:bg-surface')}>{t(v === 'health' ? 'System health' : 'Settings')}</button>
          ))}
        </div>} />
      {tab === 'health' ? <Health /> : <SettingsForm />}
    </div>
  )
}
