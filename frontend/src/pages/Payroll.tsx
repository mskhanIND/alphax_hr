import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import clsx from 'clsx'
import { AlertTriangle, Check, ChevronDown, ChevronLeft, ChevronRight, CircleDot, Info, Landmark, Users, Wallet } from 'lucide-react'
import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { Badge, Button, Card, ErrorBox, Modal, PageHeader, Select, Spinner, Stat, Textarea } from '../components/ui'
import { api } from '../lib/api'
import { fmtDate, fmtMoney, fmtMonth, fmtNumber, monthStart, shiftMonth, todayISO } from '../lib/format'
import { useI18n } from '../lib/i18n'
import { recordPath } from '../lib/links'
import { PayrollSlips } from '../components/PayrollSlips'
import { PayrollRuns } from '../components/PayrollRuns'

const FLOW = [
  { step: 'prepare', status: 'Open', done: 'Prepared', by: 'prepared' },
  { step: 'review', status: 'Prepared', done: 'Reviewed', by: 'reviewed' },
  { step: 'approve', status: 'Reviewed', done: 'Approved', by: 'approved' },
  { step: 'process', status: 'Approved', done: 'Processed', by: 'processed' },
  { step: 'close', status: 'Processed', done: 'Closed', by: null },
] as const
const ORDER = ['Open', 'Prepared', 'Reviewed', 'Approved', 'Processed', 'Closed']
const STEP_LABEL: Record<string, string> = { prepare: 'Prepare', review: 'Review', approve: 'Approve', process: 'Process payroll', close: 'Close month' }

function CheckRow({ c }: { c: any }) {
  const { t } = useI18n()
  const [open, setOpen] = useState(false)
  const icon = c.severity === 'blocker' ? <AlertTriangle className="size-4 text-red-600" /> : c.severity === 'warning'
    ? <AlertTriangle className="size-4 text-amber-600" /> : c.severity === 'info' ? <Info className="size-4 text-blue-600" /> : <Check className="size-4 text-emerald-600" />
  return (
    <li className="py-2">
      <button type="button" className="flex w-full items-center gap-3 text-start" onClick={() => setOpen(!open)} aria-expanded={open} disabled={!c.items.length && !c.hint}>
        {icon}
        <span className="flex-1 text-sm font-medium">{c.label}</span>
        {c.count > 0 && <Badge tone={c.severity === 'blocker' ? 'red' : c.severity === 'warning' ? 'amber' : 'blue'}>{c.count}</Badge>}
        {(c.items.length > 0 || c.hint) && <ChevronDown className={clsx('size-4 text-muted transition', open && 'rotate-180')} />}
      </button>
      {open && (
        <div className="mt-2 ms-7 text-sm">
          {c.hint && <p className="mb-1 text-muted">{c.hint}</p>}
          <ul className="flex flex-col gap-1">
            {c.items.map((i: any, n: number) => (
              <li key={n} className="flex flex-wrap gap-2">
                {i.doctype && i.name ? <Link className="font-medium text-brand hover:underline" to={recordPath(i.doctype, i.name)}>{i.employee_name || i.name}</Link>
                  : <span>{i.employee_name}</span>}
                {i.note && <span className="text-muted">{i.note}</span>}
              </li>
            ))}
          </ul>
          {c.count > c.items.length && <p className="text-xs text-muted">+{c.count - c.items.length}</p>}
          {c.link && <Link to={c.link} className="mt-1 inline-block text-xs font-medium text-brand hover:underline">{t('Open')} →</Link>}
        </div>
      )}
    </li>
  )
}

export default function Payroll() {
  const { t, lang } = useI18n()
  const qc = useQueryClient()
  const [month, setMonth] = useState(monthStart(todayISO()))
  const companies = useQuery({ queryKey: ['payroll-companies'], queryFn: api.payrollCompanies })
  const [company, setCompany] = useState('')
  useEffect(() => { if (!company && companies.data?.length) setCompany(companies.data[0]) }, [companies.data, company])
  const [run, setRun] = useState('')
  const runs = useQuery({ queryKey: ['payroll-runs', company, month], queryFn: () => api.payrollRunsOf(company, month), enabled: !!company })
  const q = useQuery({ queryKey: ['payroll-period', company, month, run], queryFn: () => api.payrollPeriod(company, month, run || undefined),
    enabled: !!company && !!run })
  const [act, setAct] = useState<{ step: string; label: string } | null>(null)
  const [note, setNote] = useState('')
  const [override, setOverride] = useState(false)
  const done = (data: any) => {
    qc.setQueryData(['payroll-period', company, month, run], data); setAct(null); setNote(''); setOverride(false)
    qc.invalidateQueries({ queryKey: ['payroll-runs'] })
  }
  const m = useMutation({ mutationFn: () => act!.step === 'submit_slips' ? api.payrollSubmitSlips(company, month, run || undefined)
    : api.payrollAdvance(company, month, act!.step, note || undefined, override ? 1 : 0, run || undefined), onSuccess: done })
  const ot = useMutation({ mutationFn: () => api.payrollAddOvertime(company, month, run || undefined), onSuccess: () => qc.invalidateQueries({ queryKey: ['payroll-period'] }) })
  const p = q.data
  const cl = p?.checklist
  const idx = p ? ORDER.indexOf(p.status) : 0
  const next = p ? FLOW.find((f) => f.status === p.status) : null
  const groups = cl ? [
    { title: t('Must be resolved'), items: cl.checks.filter((c: any) => c.severity === 'blocker') },
    { title: t('Check before approving'), items: cl.checks.filter((c: any) => c.severity === 'warning') },
    { title: t('For information'), items: cl.checks.filter((c: any) => c.severity === 'info') },
    { title: t('All clear'), items: cl.checks.filter((c: any) => c.severity === 'ok') },
  ].filter((g) => g.items.length) : []
  return (
    <div className="flex flex-col gap-5">
      <PageHeader title={t('Payroll control centre')} subtitle={t('Checks, approvals and processing — for the whole company, a group or single employees')} actions={
        <div className="flex flex-wrap items-center gap-2">
          {(companies.data?.length ?? 0) > 1 && (
            <Select className="w-56" value={company} onChange={(e) => setCompany(e.target.value)}>
              {companies.data!.map((c) => <option key={c} value={c}>{c}</option>)}
            </Select>
          )}
          <Button variant="secondary" size="sm" onClick={() => setMonth(shiftMonth(month, -1))}><ChevronLeft className="size-4 flip-rtl" /></Button>
          <span className="min-w-32 text-center text-sm font-medium">{fmtMonth(month, lang)}</span>
          <Button variant="secondary" size="sm" onClick={() => setMonth(shiftMonth(month, 1))}><ChevronRight className="size-4 flip-rtl" /></Button>
        </div>} />
      {company && <Card><PayrollRuns company={company} month={month} run={run} onRun={setRun} canManage={!!p?.can_approve || !!q.data?.can_approve} />
        {p?.title && <p className="mt-2 text-sm text-muted">{t('This run')}: <span className="font-medium text-ink">{p.title}</span> · {fmtNumber(p.employees ?? p.checklist?.employees ?? 0, lang)} {t('employees')}</p>}</Card>}
      {runs.isSuccess && !runs.data?.runs?.length && (
        <Card><p className="text-sm text-muted">{t('No payroll run for this month yet. Create one for the whole company, or for a department, branch, business line, cost center or chosen employees.')}</p></Card>
      )}
      {(q.isLoading && !!run) || companies.isLoading ? <Spinner /> : q.error ? <ErrorBox error={q.error} onRetry={() => q.refetch()} /> : p && (
        <>
          <Card>
            <ol className="grid gap-3 sm:grid-cols-5">
              {FLOW.map((f, i) => {
                const reached = idx > i
                const current = idx === i
                const by = f.by ? p[`${f.by}_by_name`] : null
                const on = f.by ? p[`${f.by}_on`] : null
                return (
                  <li key={f.step} className={clsx('rounded-xl border p-3', reached ? 'border-emerald-200 bg-emerald-50' : current ? 'border-brand' : 'border-line')}>
                    <div className="flex items-center gap-2 text-sm font-medium">
                      {reached ? <Check className="size-4 text-emerald-600" /> : <CircleDot className={clsx('size-4', current ? 'text-brand' : 'text-muted')} />}
                      {t(STEP_LABEL[f.step])}
                    </div>
                    {by && <div className="mt-1 text-xs text-muted">{by} · {fmtDate(on, lang)}</div>}
                  </li>
                )
              })}
            </ol>
            <div className="mt-4 flex flex-wrap items-center gap-2">
              {next && <Button onClick={() => setAct({ step: next.step, label: STEP_LABEL[next.step] })}
                disabled={next.step === 'approve' && !p.can_approve}>{t(STEP_LABEL[next.step])}</Button>}
              {p.status === 'Processed' && !p.slips.submitted && p.can_approve && (
                <Button variant="secondary" onClick={() => setAct({ step: 'submit_slips', label: 'Submit salary slips' })}>{t('Submit salary slips')}</Button>
              )}
              {['Prepared', 'Reviewed', 'Approved'].includes(p.status) && p.can_approve && (
                <Button variant="secondary" onClick={() => setAct({ step: 'reopen', label: 'Reopen' })}>{t('Reopen')}</Button>
              )}
              {p.payroll_entry && <Link className="text-sm text-brand underline" to={recordPath('Payroll Entry', p.payroll_entry)}>{p.payroll_entry} · {t(p.payroll_entry_status ?? '')}</Link>}
              {next?.step === 'approve' && !p.can_approve && <span className="text-sm text-muted">{t('An HR Manager approves payroll.')}</span>}
            </div>
          </Card>
          <div className="grid grid-cols-2 gap-3 md:grid-cols-4">
            <Stat label={t('Employees on payroll')} value={fmtNumber(cl.employees, lang)} icon={<Users className="size-4" />} />
            <Stat label={t('Salary slips')} value={fmtNumber(p.slips.slips, lang)} icon={<Wallet className="size-4" />} tone="blue"
              hint={p.slips.slips ? `${t('Draft')}: ${p.slips.draft} · ${t('Submitted')}: ${p.slips.submitted_count}` : undefined} />
            <Stat label={t('Gross pay')} value={fmtMoney(p.slips.gross, lang)} icon={<Landmark className="size-4" />} />
            <Stat label={t('Net pay')} value={fmtMoney(p.slips.net, lang)} icon={<Landmark className="size-4" />} tone="amber" />
            <Stat label={t('Total deductions')} value={fmtMoney(p.slips.deductions, lang)} tone="red" />
            <Stat label={t('GOSI (employee share)')} value={fmtMoney(p.slips.gosi, lang)} tone="blue" />
            <Stat label={t('Loan repayments')} value={fmtMoney(p.slips.loans, lang)} />
            <Stat label={t('Penalties')} value={fmtMoney(p.slips.penalties, lang)} tone="red" />
          </div>
          {p.payroll_entry_status === 'Queued' && <p className="rounded-xl bg-blue-50 p-3 text-sm text-blue-900">{t('Salary slips are being created in the background. Refresh in a minute.')}</p>}
          {p.payroll_entry && <PayrollSlips company={company} month={month} run={run || undefined} closed={p.status === 'Closed'} canManage={p.can_approve} />}
          <div className="grid gap-5 lg:grid-cols-3">
            <Card className="lg:col-span-2" title={t('Payroll checklist')}
              subtitle={`${cl.blockers} ${t('blocking')} · ${cl.warnings} ${t('to check')}`}
              action={<Button size="sm" variant="secondary" loading={ot.isPending} onClick={() => ot.mutate()}>{t('Add overtime pay')}</Button>}>
              {ot.data && <p className="mb-2 text-sm text-emerald-700">{t('Overtime added for')} {ot.data.created.length} · {t('skipped')} {ot.data.skipped.length}</p>}
              {ot.error && <ErrorBox error={ot.error} />}
              {groups.map((g) => (
                <div key={g.title} className="mb-3">
                  <div className="text-xs font-semibold uppercase tracking-wide text-muted">{g.title}</div>
                  <ul className="divide-y divide-line">{g.items.map((c: any) => <CheckRow key={c.key} c={c} />)}</ul>
                </div>
              ))}
            </Card>
            <Card title={t('Activity')}>
              {!p.trail.length ? <p className="text-sm text-muted">—</p> : (
                <ol className="flex flex-col gap-2 text-sm">
                  {[...p.trail].reverse().map((e: any) => e.kind === 'changed'
                    ? { ...e, changes: (e.changes ?? []).filter((c: any) => ['status', 'payroll_entry', 'notes'].includes(c.field)) } : e)
                    .filter((e: any) => e.kind !== 'changed' || e.changes.length).map((e: any, i: number) => (
                    <li key={i}>
                      <div className="font-medium">{e.name ?? e.user}</div>
                      <div className="text-xs text-muted">{fmtDate(e.at, lang)} · {e.text ?? (e.changes ? e.changes.map((c: any) => `${c.label ?? c.field}: ${c.field === 'status' ? t(c.to ?? '') : c.to ?? ''}`).join(', ') : t(e.kind))}</div>
                    </li>
                  ))}
                </ol>
              )}
            </Card>
          </div>
        </>
      )}
      <Modal open={!!act} onClose={() => setAct(null)} title={act ? `${t(act.label)} · ${fmtMonth(month, lang)}` : ''}
        footer={<><Button variant="secondary" onClick={() => setAct(null)}>{t('Cancel')}</Button>
          <Button loading={m.isPending} disabled={override && !note.trim()} onClick={() => m.mutate()}>{act ? t(act.label) : ''}</Button></>}>
        {cl && cl.blockers > 0 && ['prepare', 'approve', 'process'].includes(act?.step ?? '') && (
          <div className="mb-3 rounded-xl bg-red-50 p-3 text-sm text-red-800">
            {cl.blockers} {t('blocking item(s) are still open.')}
            {p?.can_approve && <label className="mt-2 flex items-center gap-2"><input type="checkbox" checked={override} onChange={(e) => setOverride(e.target.checked)} />{t('Continue anyway (HR Manager, note required)')}</label>}
          </div>
        )}
        {act?.step === 'process' && <p className="mb-3 text-sm text-muted">{t('Creates the Payroll Entry in ERPNext and the draft salary slips for every employee with a salary structure.')}</p>}
        <Textarea placeholder={t('Note (optional)')} value={note} onChange={(e) => setNote(e.target.value)} />
        {m.error && <div className="mt-3"><ErrorBox error={m.error} /></div>}
      </Modal>
    </div>
  )
}
