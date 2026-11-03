import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import clsx from 'clsx'
import { Plus, Trash2, X } from 'lucide-react'
import { useEffect, useState } from 'react'
import { api } from '../lib/api'
import { useI18n } from '../lib/i18n'
import { LinkInput } from './LinkInput'
import { Badge, Button, ErrorBox, Field, Modal, Select } from './ui'

const SCOPES = ['Company', 'Department', 'Branch', 'Business line', 'Cost center', 'Employees']

/** Payroll runs of the month: the whole company, a group (department, branch, business line, cost center) or chosen employees. */
export function PayrollRuns({ company, month, run, onRun, canManage }: {
  company: string; month: string; run: string; onRun: (name: string) => void; canManage: boolean
}) {
  const { t } = useI18n()
  const qc = useQueryClient()
  const q = useQuery({ queryKey: ['payroll-runs', company, month], queryFn: () => api.payrollRunsOf(company, month), enabled: !!company })
  const [open, setOpen] = useState(false)
  const runs: any[] = q.data?.runs ?? []
  useEffect(() => {
    if (q.data && runs.length && !runs.some((r) => r.name === run)) onRun(runs[0].name)
    if (q.data && !runs.length && run) onRun('')
  }, [q.data]) // eslint-disable-line react-hooks/exhaustive-deps
  const del = useMutation({ mutationFn: (name: string) => api.payrollDeleteRun(name), onSuccess: () => { onRun(''); qc.invalidateQueries({ queryKey: ['payroll-runs'] }) } })
  return (
    <div className="flex flex-wrap items-center gap-2" data-testid="payroll-runs">
      <span className="text-sm text-muted">{t('Payroll runs')}:</span>
      {runs.map((r) => (
        <span key={r.name} className={clsx('flex items-center gap-1 rounded-full border px-3 py-1 text-sm', r.name === run ? 'border-brand bg-brand-50 text-brand-700' : 'border-line bg-white')}>
          <button onClick={() => onRun(r.name)} className="font-medium">{r.title}</button>
          <Badge tone={r.status === 'Closed' ? 'green' : r.status === 'Open' ? 'gray' : 'amber'}>{t(r.status)}</Badge>
          {canManage && !r.payroll_entry && r.name === run && (
            <button aria-label={t('Delete')} className="text-muted hover:text-red-600" onClick={() => del.mutate(r.name)}><Trash2 className="size-3.5" /></button>
          )}
        </span>
      ))}
      {!runs.length && q.data && <span className="text-sm text-muted">{t('None yet for this month.')}</span>}
      <Button size="sm" variant="secondary" onClick={() => setOpen(true)}><Plus className="size-4" />{t('New payroll run')}</Button>
      {del.error && <ErrorBox error={del.error} />}
      <NewRun open={open} onClose={() => setOpen(false)} company={company} month={month} hasRuns={runs.length > 0}
        onCreated={(name) => { setOpen(false); qc.invalidateQueries({ queryKey: ['payroll-runs'] }); onRun(name) }} />
    </div>
  )
}

function NewRun({ open, onClose, company, month, hasRuns, onCreated }: {
  open: boolean; onClose: () => void; company: string; month: string; hasRuns: boolean; onCreated: (name: string) => void
}) {
  const { t } = useI18n()
  const [scope, setScope] = useState(hasRuns ? 'Department' : 'Company')
  const [value, setValue] = useState('')
  const [emps, setEmps] = useState<{ value: string; label: string }[]>([])
  const [pick, setPick] = useState('')
  const addPick = () => { const v = pick.trim(); if (v && !emps.some((e) => e.value === v)) setEmps([...emps, { value: v, label: v }]); setPick('') }
  const opts = useQuery({ queryKey: ['payroll-scope', company], queryFn: () => api.payrollScopeOptions(company), enabled: open && !!company })
  useEffect(() => { setValue('') }, [scope])
  const m = useMutation({
    mutationFn: () => api.payrollCreateRun(company, month, scope, scope === 'Employees' ? emps.map((e) => e.value).join('\n') : value || undefined),
    onSuccess: (d: any) => { setEmps([]); setValue(''); onCreated(d.name) },
  })
  const list: string[] = opts.data?.[scope] ?? []
  const ready = scope === 'Company' || (scope === 'Employees' ? emps.length > 0 : !!value)
  return (
    <Modal open={open} onClose={onClose} title={t('New payroll run')}
      footer={<><Button variant="secondary" onClick={onClose}>{t('Cancel')}</Button>
        <Button disabled={!ready} loading={m.isPending} onClick={() => m.mutate()}>{t('Create run')}</Button></>}>
      <div className="flex flex-col gap-3">
        <p className="text-sm text-muted">{t('Process the whole company at once, or one group at a time. Each employee can be in only one run per month.')}</p>
        <Field label={t('Run payroll for')}>
          <Select value={scope} onChange={(e) => setScope(e.target.value)}>
            {SCOPES.map((s) => <option key={s} value={s}>{t(s === 'Company' ? 'Whole company' : s === 'Employees' ? 'Selected employees (single or bulk)' : s)}</option>)}
          </Select>
        </Field>
        {['Department', 'Branch', 'Business line', 'Cost center'].includes(scope) && (
          <Field label={t(scope)} hint={scope === 'Business line' && !opts.data?.business_line_field ? t('No business line field found on Employee. Set it in Settings → Salary.') : undefined}>
            <Select value={value} onChange={(e) => setValue(e.target.value)}>
              <option value="">{t('Choose…')}</option>
              {list.map((v) => <option key={v} value={v}>{v}</option>)}
            </Select>
          </Field>
        )}
        {scope === 'Employees' && (
          <Field label={t('Employees')} hint={t('One employee = single salary processing.')}>
            <div className="flex flex-col gap-2">
              <div className="flex gap-2">
                <div className="flex-1"><LinkInput doctype="Employee" value={pick} onChange={setPick} /></div>
                <Button size="sm" variant="secondary" disabled={!pick.trim()} onClick={addPick}><Plus className="size-4" />{t('Add')}</Button>
              </div>
              <div className="flex flex-wrap gap-1.5">
                {emps.map((e) => (
                  <span key={e.value} className="flex items-center gap-1 rounded-full bg-surface px-2.5 py-1 text-xs">
                    {e.label}<button aria-label={t('Remove')} onClick={() => setEmps(emps.filter((x) => x.value !== e.value))}><X className="size-3" /></button>
                  </span>
                ))}
              </div>
            </div>
          </Field>
        )}
        {m.error && <ErrorBox error={m.error} />}
      </div>
    </Modal>
  )
}
