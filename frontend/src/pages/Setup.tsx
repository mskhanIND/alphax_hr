import { PageAccess } from '../components/PageAccess'
import { PayrollComponents } from '../components/PayrollComponents'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import clsx from 'clsx'
import { AlertTriangle, CheckCircle2, RefreshCw, XCircle } from 'lucide-react'
import { useEffect, useState } from 'react'
import { Link, useLocation } from 'react-router-dom'
import { FieldInput } from '../components/FieldInput'
import { LinkInput } from '../components/LinkInput'
import { Button, Card, ErrorBox, Field, Input, PageHeader, Select, Spinner, Stat, Modal } from '../components/ui'
import { api } from '../lib/api'
import { useSession } from '../lib/session'
import { useI18n } from '../lib/i18n'

const CHECK_LABEL: Record<string, string> = {
  scheduler: 'Scheduler', workers: 'Background workers', alphax_jobs: 'AlphaX scheduled jobs', alphax_job_failures: 'Failed AlphaX jobs (24h)',
  error_log_24h: 'Errors logged (24h)', outgoing_email: 'Outgoing email', employee_row_size: 'Employee table space',
  default_company: 'Default company', holiday_lists: 'Holiday lists', leave_approver: 'Leave approvers', shift_approver: 'Shift approvers',
  reports_to: 'Reporting managers', user_account: 'Employee user accounts', salary_mapping: 'Salary component mapping',
  annual_leave: 'Annual leave', statutory_leave: 'Statutory leave types', gosi_rates: 'GOSI rates', broken_links: 'Employee values missing from their lists', print_images: 'Images missing from letter heads and payslips', check_failed: 'Check could not run', broken_scripts: 'Server scripts using fields of removed apps', orphan_mandatory: 'Mandatory fields left by removed apps', save_test: 'Saving an employee (test, undone)',
  documents_expired: 'Expired documents', documents_expiring: 'Documents expiring (30 days)', mandatory_missing: 'Employees missing mandatory data',
  no_salary: 'Employees without salary', approvals_waiting: 'Approvals waiting over 3 days',
}
const ICON = {
  ok: <CheckCircle2 className="size-5 text-emerald-600" />,
  warn: <AlertTriangle className="size-5 text-amber-500" />,
  error: <XCircle className="size-5 text-red-600" />,
}

function FixPanel({ check, onClose, onDone }: { check: any; onClose: () => void; onDone: () => void }) {
  const { t } = useI18n()
  const q = useQuery<any>({ queryKey: ['affected', check.key], queryFn: () => api.affected(check.key) })
  const [sel, setSel] = useState<Set<string>>(new Set())
  const [value, setValue] = useState('')
  const fix = useMutation({ mutationFn: () => api.bulkFix(check.key, [...sel], value), onSuccess: () => { setSel(new Set()); q.refetch(); onDone() } })
  const rows: any[] = q.data?.rows ?? []
  return (
    <div className="fixed inset-0 z-40 flex justify-end bg-slate-900/30" onMouseDown={onClose}>
      <aside role="dialog" aria-label={t(CHECK_LABEL[check.key] ?? check.key)} className="h-full w-full max-w-2xl overflow-y-auto bg-white p-5 shadow-xl" onMouseDown={(e) => e.stopPropagation()}>
        <div className="mb-1 flex items-center justify-between">
          <span className="text-lg font-semibold">{t(CHECK_LABEL[check.key] ?? check.key)}</span>
          <button onClick={onClose} className="rounded-lg p-1 text-muted hover:bg-surface" aria-label={t('Close')}>✕</button>
        </div>
        {check.detail && <p className="mb-4 text-sm text-muted">{check.detail}</p>}
        {q.isLoading ? <Spinner /> : q.error ? <ErrorBox error={q.error} /> : (
          <>
            {q.data.set_field && (
              <div className="mb-4 flex flex-wrap items-end gap-2 rounded-xl border border-line bg-surface p-3">
                <div className="min-w-60 flex-1">
                  <Field label={`${t('Set for selected')} (${sel.size})`}><LinkInput doctype={q.data.link_doctype} value={value} onChange={setValue} /></Field>
                  {q.data.suggestions?.length > 0 && <div className="mt-1 flex flex-wrap gap-1 text-xs">{q.data.suggestions.map((sg: string) => <button key={sg} className="rounded bg-white px-2 py-0.5 ring-1 ring-line hover:bg-brand-50" onClick={() => setValue(sg)}>{sg}</button>)}</div>}
                </div>
                <Button disabled={!sel.size || !value} loading={fix.isPending} onClick={() => fix.mutate()}>{t('Apply')}</Button>
                {check.key === 'holiday_lists' && <Link to="/holiday-lists" className="text-sm font-medium text-brand hover:underline">{t('Extend or create a holiday list')}</Link>}
              </div>
            )}
            {fix.data && <p className="mb-3 text-sm text-emerald-700">{t('Updated')}: {fix.data.done.length}{fix.data.failed.length ? ` · ${t('Not updated')}: ${fix.data.failed.length}` : ''}</p>}
            {fix.data?.failed?.length > 0 && <ul className="mb-3 list-disc rounded-xl bg-amber-50 p-3 ps-8 text-sm text-amber-900">{fix.data.failed.map((f: any) => <li key={f.employee}><b>{f.employee}</b>: {f.error.replace(/<[^>]+>/g, '')}</li>)}</ul>}
            {fix.error && <ErrorBox error={fix.error} />}
            {!rows.length ? <p className="text-sm text-emerald-700">{t('All fixed.')}</p> : (
              <table className="w-full text-sm">
                <thead className="text-xs text-muted"><tr className="border-b border-line">
                  {q.data.set_field && <th className="w-8 pb-2"><input type="checkbox" className="size-4 accent-[var(--color-brand)]" aria-label={t('Select all')} checked={sel.size === rows.length} onChange={(e) => setSel(e.target.checked ? new Set(rows.map((r) => r.name)) : new Set())} /></th>}
                  <th className="pb-2 text-start font-medium">{t('Employee')}</th><th className="pb-2 text-start font-medium">{t('Department')}</th><th className="pb-2 text-start font-medium">{t('Details')}</th>
                </tr></thead>
                <tbody className="divide-y divide-line">
                  {rows.map((r) => (
                    <tr key={r.name + (r.note ?? '')}>
                      {q.data.set_field && <td className="py-2"><input type="checkbox" className="size-4 accent-[var(--color-brand)]" checked={sel.has(r.name)} onChange={() => setSel((s) => { const n = new Set(s); if (n.has(r.name)) n.delete(r.name); else n.add(r.name); return n })} /></td>}
                      <td className="py-2"><Link to={`/people/${encodeURIComponent(r.name)}`} className="font-medium text-brand hover:underline">{r.employee_name}</Link><div className="text-xs text-muted">{r.name}</div></td>
                      <td className="py-2">{r.department ?? '—'}</td>
                      <td className="py-2 text-muted">{r.note ?? '—'}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
          </>
        )}
      </aside>
    </div>
  )
}

function PayslipActions({ can }: { can: boolean }) {
  const { t } = useI18n()
  const [html, setHtml] = useState<string | null>(null)
  const slip = useQuery({ queryKey: ['latest-slip'], queryFn: api.latestSlip })
  const pv = useMutation({ mutationFn: () => api.payslipPreview(slip.data!), onSuccess: (d: any) => setHtml(d.html) })
  const pf = useMutation({ mutationFn: () => api.installPayslipFormat() })
  return (
    <div className="mt-5 flex flex-wrap items-center gap-2 border-t border-line pt-4">
      <Button variant="secondary" size="sm" disabled={!slip.data} loading={pv.isPending} onClick={() => pv.mutate()}>{t('Preview payslip')}</Button>
      {can && <Button variant="secondary" size="sm" loading={pf.isPending} onClick={() => pf.mutate()}>{t('Use this payslip in ERPNext printing')}</Button>}
      <span className="text-xs text-muted">{t('Save settings first; the preview uses the latest salary slip.')}</span>
      {pf.isSuccess && <span className="text-sm text-emerald-700">{t('Print format "AlphaX Salary Slip" is now the default.')}</span>}
      {(pv.error || pf.error) && <ErrorBox error={pv.error || pf.error} />}
      {html && <Modal open wide onClose={() => setHtml(null)} title={t('Payslip preview')}><div className="overflow-x-auto" dangerouslySetInnerHTML={{ __html: html }} /></Modal>}
    </div>
  )
}

function StatusList({ onSettings }: { onSettings: () => void }) {
  const { t } = useI18n()
  const qc = useQueryClient()
  const q = useQuery<any>({ queryKey: ['status', 'hr'], queryFn: api.hrStatus })
  const [panel, setPanel] = useState<any>(null)
  const allow = useMutation({ mutationFn: api.allowStatutory, onSuccess: () => q.refetch() })
  const links = useMutation({ mutationFn: api.createMissingLinks, onSuccess: () => q.refetch() })
  const scripts = useMutation({ mutationFn: api.disableBrokenScripts, onSuccess: () => q.refetch() })
  const relax = useMutation({ mutationFn: api.relaxOrphanFields, onSuccess: () => q.refetch() })
  if (q.isLoading) return <Spinner />
  if (q.error) return <ErrorBox error={q.error} onRetry={() => q.refetch()} />
  const d = q.data
  const groups: string[] = [...new Set<string>(d.checks.map((c: any) => c.group))]
  const order = (c: any) => ['error', 'warn', 'ok'].indexOf(c.status)
  const fixButton = (c: any) => {
    if (c.status === 'ok') return null
    if (c.fix === 'employees') return <Button size="sm" variant="secondary" onClick={() => setPanel(c)}>{t('Fix')}</Button>
    if (c.fix === 'settings') return <Button size="sm" variant="secondary" onClick={onSettings}>{t('Fix')}</Button>
    if (c.fix === 'create_missing_links') return <Button size="sm" variant="secondary" loading={links.isPending} onClick={() => links.mutate()}>{t('Create missing values')}</Button>
    if (c.fix === 'disable_scripts') return <Button size="sm" variant="secondary" loading={scripts.isPending} onClick={() => scripts.mutate()}>{t('Disable these scripts')}</Button>
    if (c.fix === 'relax_orphans') return <Button size="sm" variant="secondary" loading={relax.isPending} onClick={() => relax.mutate()}>{t('Make them optional')}</Button>
    if (c.fix === 'allow_leave_types') return <Button size="sm" variant="secondary" loading={allow.isPending} onClick={() => allow.mutate()}>{t('Allow all')}</Button>
    if (c.link?.startsWith('/app')) return <a href={c.link} target="_blank" rel="noreferrer"><Button size="sm" variant="ghost">{t('Open')}</Button></a>
    if (c.link) return <Link to={c.link}><Button size="sm" variant="secondary">{t('Fix')}</Button></Link>
    return null
  }
  return (
    <div className="flex flex-col gap-5">
      <div className="grid grid-cols-3 gap-3">
        <Stat label={t('Healthy')} value={d.counts.ok} />
        <Stat label={t('Warnings')} value={d.counts.warn} tone="amber" />
        <Stat label={t('Problems')} value={d.counts.error} tone="red" />
      </div>
      {links.data && <p className="rounded-xl bg-emerald-50 p-3 text-sm text-emerald-800">{t('Created')}: {links.data.created.join(', ') || '—'}{links.data.skipped.length ? ` · ${t('Needs the desk')}: ${links.data.skipped.join(', ')}` : ''}</p>}
      {(links.error || scripts.error || relax.error) && <ErrorBox error={links.error || scripts.error || relax.error} />}
      {groups.map((g) => (
        <Card key={g} title={t(g)} action={<Button size="sm" variant="ghost" loading={q.isFetching} onClick={() => q.refetch()}><RefreshCw className="size-4" />{t('Re-check')}</Button>}>
          <ul className="divide-y divide-line">
            {d.checks.filter((c: any) => c.group === g).sort((a: any, b: any) => order(a) - order(b)).map((c: any) => (
              <li key={c.key} className="flex items-start gap-3 py-3">
                {ICON[c.status as keyof typeof ICON]}
                <div className="min-w-0 flex-1">
                  <div className="flex flex-wrap items-baseline justify-between gap-2">
                    <span className="font-medium">{t(CHECK_LABEL[c.key] ?? c.key)}</span>
                    <span className={clsx('text-sm tabular-nums', c.status === 'ok' ? 'text-muted' : c.status === 'warn' ? 'text-amber-800' : 'text-red-700')}>{c.value ?? ''}</span>
                  </div>
                  {c.detail && <p className="mt-0.5 text-sm text-muted">{c.detail}</p>}
                </div>
                <div className="shrink-0">{fixButton(c)}</div>
              </li>
            ))}
          </ul>
        </Card>
      ))}
      {panel && <FixPanel check={panel} onClose={() => setPanel(null)} onDone={() => qc.invalidateQueries({ queryKey: ['status', 'hr'] })} />}
    </div>
  )
}

type Group = { key: string; label: string; guide: string; sections: string[] }
const GROUPS: Group[] = [
  { key: 'company', label: 'Company & branding', sections: ['general_section', 'documents_section'],
    guide: 'App name, logo and colours, default language and company, and which documents AlphaX tracks.' },
  { key: 'portal', label: 'Portal & pages', sections: ['portal_section', 'pages_section'],
    guide: 'Keep HR and employees in AlphaX instead of the Desk, the sign-in page, and which pages each role sees.' },
  { key: 'employees', label: 'Employees & salary', sections: ['employee_section', 'salary_section'],
    guide: 'Rules checked when an employee is saved (IDs, IBAN, contract) and how new salaries are entered.' },
  { key: 'attendance', label: 'Attendance & check-in', sections: ['checkin_section'],
    guide: 'Where and how employees check in, grace minutes and late/early permissions.' },
  { key: 'leave', label: 'Leave', sections: ['leave_section'],
    guide: 'Annual leave type and counting rules. Leave types, statutory leave and approval delays are in Leave setup.' },
  { key: 'payroll', label: 'Payroll, GOSI & loans', sections: ['gosi_section', 'loans_section', 'nitaqat_section'],
    guide: 'Payroll components, GOSI component mapping, loan and advance limits, and the Nitaqat estimate.' },
  { key: 'accruals', label: 'Accruals', sections: ['accruals_section'],
    guide: 'Accounts and basis for the monthly end-of-service and annual-leave accruals.' },
  { key: 'documents', label: 'Payslips & letters', sections: ['payslip_section'],
    guide: 'Payslip layout, letter head and signatures on official documents.' },
  { key: 'notifications', label: 'Notifications', sections: ['push_section', 'notify_section'],
    guide: 'Phone notifications. Who is told about what is set on the Notifications page.' },
]

function SettingsForm() {
  const { t } = useI18n()
  const qc = useQueryClient()
  const q = useQuery<any>({ queryKey: ['settings'], queryFn: api.getSettings })
  const [values, setValues] = useState<Record<string, any>>({})
  const [map, setMap] = useState<any[]>([])
  const [group, setGroup] = useState<string>(() => { try { return sessionStorage.getItem('alphax-settings-group') || 'company' } catch { return 'company' } })
  const [find, setFind] = useState('')
  useEffect(() => { if (q.data) { setValues(q.data.values); setMap(q.data.component_map) } }, [q.data])
  const save = useMutation({ mutationFn: () => api.saveSettings({ values, component_map: map }), onSuccess: (d) => { qc.setQueryData(['settings'], d); qc.invalidateQueries({ queryKey: ['health'] }) } })
  const same = (a: any, b: any) => (a ?? '') === (b ?? '') || String(a ?? '') === String(b ?? '')
  const changed = q.data ? Object.keys(values).filter((k) => !same(values[k], q.data.values[k])) : []
  const mapChanged = q.data ? JSON.stringify(map) !== JSON.stringify(q.data.component_map) : false
  const dirty = changed.length > 0 || mapChanged
  useEffect(() => {
    if (!dirty) return
    const warn = (e: BeforeUnloadEvent) => { e.preventDefault(); e.returnValue = '' }
    window.addEventListener('beforeunload', warn)
    return () => window.removeEventListener('beforeunload', warn)
  }, [dirty])
  if (q.isLoading) return <Spinner />
  if (q.error) return <ErrorBox error={q.error} onRetry={() => q.refetch()} />
  const can = q.data.can_edit
  const sections: any[] = q.data.sections
  const known = new Set(GROUPS.flatMap((g) => g.sections))
  const other = sections.filter((x) => !known.has(x.key)).map((x) => x.key)
  const groups: Group[] = [...GROUPS.filter((g) => g.sections.some((k) => sections.some((x) => x.key === k)) || g.key === 'payroll'),
    ...(other.length ? [{ key: 'other', label: 'Other', sections: other, guide: '' }] : []),
    { key: 'more', label: 'More setup', sections: [], guide: 'Other places where AlphaX is set up.' }]
  const fieldGroup: Record<string, string> = {}
  const fieldLabel: Record<string, string> = {}
  for (const g of groups) for (const sec of sections.filter((x) => g.sections.includes(x.key))) for (const f of sec.fields) { fieldGroup[f.fieldname] = g.key; fieldLabel[f.fieldname] = f.label }
  const dirtyGroups = new Set([...changed.map((k) => fieldGroup[k]), ...(mapChanged ? ['payroll'] : [])])
  const pick = (k: string) => { setGroup(k); setFind(''); try { sessionStorage.setItem('alphax-settings-group', k) } catch { /* private mode */ } }
  const needle = find.trim().toLowerCase()
  const matches = needle ? sections.flatMap((sec) => sec.fields.filter((f: any) => `${f.label} ${f.description ?? ''}`.toLowerCase().includes(needle)).map((f: any) => ({ ...f, group: fieldGroup[f.fieldname] }))) : []
  const g = groups.find((x) => x.key === group) ?? groups[0]
  const renderField = (f: any) => (
    f.fieldtype === 'Check' ? (
      <label key={f.fieldname} className={clsx('flex items-start gap-2 text-sm sm:col-span-2', changed.includes(f.fieldname) && 'rounded-lg bg-amber-50 p-1.5')}>
        <input type="checkbox" className="mt-0.5 size-4 accent-[var(--color-brand)]" disabled={!can} checked={!!Number(values[f.fieldname])}
          onChange={(e) => setValues({ ...values, [f.fieldname]: e.target.checked ? 1 : 0 })} />
        <span><span className="font-medium">{f.label}</span>{f.description && <span className="block text-xs text-muted">{f.description}</span>}</span>
      </label>
    ) : (
      <div key={f.fieldname} className={clsx(changed.includes(f.fieldname) && 'rounded-lg bg-amber-50 p-1.5')}>
        <Field label={f.label} hint={f.description ?? undefined}>
          <fieldset disabled={!can}><FieldInput spec={f} value={values[f.fieldname]} attachTo={['AlphaX HR Settings', 'AlphaX HR Settings']} onChange={(v) => setValues({ ...values, [f.fieldname]: v })} /></fieldset>
        </Field>
      </div>
    )
  )
  return (
    <div className="flex flex-col gap-5 lg:flex-row lg:items-start">
      <nav className="flex shrink-0 flex-col gap-2 lg:sticky lg:top-4 lg:w-60" aria-label={t('Settings sections')}>
        <Input placeholder={t('Find a setting…')} value={find} onChange={(e) => setFind(e.target.value)} />
        <div className="flex gap-1 overflow-x-auto lg:flex-col">
          {groups.map((x) => (
            <button key={x.key} onClick={() => pick(x.key)} aria-current={x.key === g.key && !needle ? 'page' : undefined}
              className={clsx('flex items-center justify-between gap-2 whitespace-nowrap rounded-xl px-3 py-2 text-start text-sm',
                x.key === g.key && !needle ? 'bg-brand text-white' : 'text-ink hover:bg-surface')}>
              {t(x.label)}{dirtyGroups.has(x.key) && <span className="size-2 rounded-full bg-amber-400" title={t('Unsaved changes')} />}
            </button>
          ))}
        </div>
      </nav>
      <div className="flex min-w-0 flex-1 flex-col gap-5 pb-24">
        {needle ? (
          <Card title={`${t('Settings matching')} “${find}”`}>
            {!matches.length ? <p className="text-sm text-muted">{t('No setting matches.')}</p> : (
              <div className="flex flex-col gap-4">
                {matches.map((f: any) => (
                  <div key={f.fieldname}>
                    <button className="mb-1 text-xs text-brand hover:underline" onClick={() => pick(f.group)}>{t(groups.find((x) => x.key === f.group)?.label ?? '')} →</button>
                    <div className="grid gap-4 sm:grid-cols-2">{renderField(f)}</div>
                  </div>
                ))}
              </div>
            )}
          </Card>
        ) : <>
          {g.guide && <div className="rounded-xl border border-brand/20 bg-brand-50 p-4 text-sm text-brand"><b>{t(g.label)}.</b> {t(g.guide)}</div>}
          {g.key === 'payroll' && <PayrollComponents />}
          {g.key === 'portal' && <PageAccess />}
          {sections.filter((x) => g.sections.includes(x.key)).map((sec) => (
            <Card key={sec.key} title={sec.label}>
              <div className="grid gap-4 sm:grid-cols-2">{sec.fields.map(renderField)}</div>
              {sec.key === 'payslip_section' && <PayslipActions can={can} />}
              {sec.key === 'checkin_section' && <p className="mt-4 text-sm"><Link className="text-brand underline" to="/work-locations">{t('Work locations (check-in areas)')}</Link></p>}
              {sec.key === 'notify_section' && <p className="mt-4 text-sm"><Link className="text-brand underline" to="/notifications-setup">{t('Who is told about what')}</Link></p>}
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
          {g.key === 'more' && (
            <Card title={t('More setup')}>
              <div className="flex flex-wrap gap-2">
                <Link to="/leave-setup"><Button variant="secondary">{t('Leave setup')}</Button></Link>
                <Link to="/roster"><Button variant="secondary">{t('Roster & week-offs')}</Button></Link>
                <Link to="/notifications-setup"><Button variant="secondary">{t('Notifications')}</Button></Link>
                <Link to="/compliance"><Button variant="secondary">{t('Data readiness')}</Button></Link>
                <a href="/app/gosi-contribution-rate" target="_blank" rel="noreferrer"><Button variant="secondary">{t('GOSI rates')}</Button></a>
                <Link to="/holiday-lists"><Button variant="secondary">{t('Holiday lists')}</Button></Link>
                <a href="/app/alphax-hr-settings" target="_blank" rel="noreferrer"><Button variant="secondary">{t('System health (Desk)')}</Button></a>
              </div>
            </Card>
          )}
        </>}
        {save.error && <ErrorBox error={save.error} />}
      </div>
      {can && (dirty || save.isSuccess) && (
        <div className="fixed inset-x-0 bottom-0 z-30 border-t border-line bg-white/95 px-4 py-3 shadow-lg backdrop-blur lg:ps-72">
          <div className="mx-auto flex max-w-6xl flex-wrap items-center gap-3">
            {dirty ? <>
              <span className="text-sm font-medium">{changed.length + (mapChanged ? 1 : 0)} {t('unsaved changes')}:</span>
              <span className="min-w-0 flex-1 truncate text-sm text-muted">
                {[...changed.map((k) => fieldLabel[k] ?? k), ...(mapChanged ? [t('Salary component mapping')] : [])].join(' · ')}
              </span>
              <Button variant="secondary" size="sm" onClick={() => { setValues(q.data.values); setMap(q.data.component_map); save.reset() }}>{t('Discard')}</Button>
              <Button size="sm" loading={save.isPending} onClick={() => save.mutate()}>{t('Save settings')}</Button>
            </> : <span className="text-sm text-emerald-700">{t('Saved')}</span>}
          </div>
        </div>
      )}
    </div>
  )
}

export default function Setup() {
  const { t } = useI18n()
  const loc = useLocation()
  const s = useSession()
  // Technical checks (system health) and the employee field map live in the Desk: AlphaX HR Settings.
  const isLead = !!s.persona.system_manager || !!s.persona.hr_manager  // overall HR status: HR Managers (and System Managers)
  type Tab = 'hr' | 'settings'
  const tabs: Tab[] = [...(isLead ? ['hr' as Tab] : []), 'settings']
  const [tab, setTab] = useState<Tab>(loc.hash === '#settings' || !isLead ? 'settings' : 'hr')
  const tabLabel: Record<Tab, string> = { hr: 'HR status', settings: 'Settings' }
  return (
    <div className="flex flex-col gap-5">
      <PageHeader title={t('HR status & setup')} subtitle={t('Where HR data needs attention, and how AlphaX is set up — in one place.')}
        actions={<div className="flex rounded-xl border border-line p-0.5" role="tablist">
          {tabs.map((v) => (
            <button key={v} role="tab" aria-selected={tab === v} onClick={() => setTab(v)}
              className={clsx('rounded-lg px-3 py-1.5 text-sm', tab === v ? 'bg-brand text-white' : 'text-muted hover:bg-surface')}>{t(tabLabel[v])}</button>
          ))}
        </div>} />
      {tab === 'hr' && isLead ? <StatusList onSettings={() => setTab('settings')} /> : <SettingsForm />}
    </div>
  )
}
