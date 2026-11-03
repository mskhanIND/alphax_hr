import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import clsx from 'clsx'
import { Plus, Star, Trash2, X } from 'lucide-react'
import { useState } from 'react'
import { Link } from 'react-router-dom'
import { AppraisalForm } from '../components/AppraisalForm'
import { LinkInput } from '../components/LinkInput'
import { Badge, Button, Card, Empty, ErrorBox, Field, Input, Modal, PageHeader, Select, Spinner, StatusBadge, Table } from '../components/ui'
import { api } from '../lib/api'
import { fmtDate, fmtNumber } from '../lib/format'
import { useI18n } from '../lib/i18n'
import { recordPath } from '../lib/links'

const STAGE_TONE: Record<string, string> = { 'Waiting for self': 'gray', 'Self done': 'amber', Reviewed: 'blue', Final: 'green' }

export function AppraisalTable({ rows }: { rows: any[] }) {
  const { t, lang } = useI18n()
  return (
    <Table head={[t('Employee'), t('Appraisal cycle'), t('Goals'), t('Feedback'), t('Self'), t('Final score'), t('Status')]}>
      {rows.map((r) => (
        <tr key={r.name}>
          <td className="py-2"><Link className="font-medium text-brand hover:underline" to={recordPath('Appraisal', r.name)}>{r.employee_name}</Link>
            <div className="text-xs text-muted">{r.department}</div></td>
          <td className="text-sm">{r.appraisal_cycle}<div className="text-xs text-muted">{fmtDate(r.start_date, lang)} → {fmtDate(r.end_date, lang)}</div></td>
          <td>{fmtNumber(r.total_score, lang, 1)}</td><td>{fmtNumber(r.avg_feedback_score, lang, 1)}</td>
          <td>{fmtNumber(r.self_score, lang, 1)}</td><td className="font-semibold">{fmtNumber(r.final_score, lang, 2)}</td>
          <td><StatusBadge status={r.status} /></td>
        </tr>
      ))}
    </Table>
  )
}

function WeightRows({ rows, setRows, keyName, label }: { rows: any[]; setRows: (r: any[]) => void; keyName: string; label: string }) {
  const { t } = useI18n()
  const total = rows.reduce((s, r) => s + (Number(r.weight) || 0), 0)
  return (
    <div>
      <div className="mb-1 flex items-center justify-between text-sm font-medium">{label}
        <span className={clsx('text-xs', total === 100 ? 'text-emerald-700' : 'text-red-700')}>{t('Total')}: {total}%</span></div>
      <div className="flex flex-col gap-2">
        {rows.map((r, i) => (
          <div key={i} className="flex gap-2">
            <Input className="flex-1" value={r[keyName]} placeholder={label} onChange={(e) => setRows(rows.map((x, j) => (j === i ? { ...x, [keyName]: e.target.value } : x)))} />
            <Input className="!w-24" type="number" min={0} max={100} value={r.weight} onChange={(e) => setRows(rows.map((x, j) => (j === i ? { ...x, weight: Number(e.target.value) } : x)))} />
            <Button size="sm" variant="ghost" aria-label={t('Remove')} onClick={() => setRows(rows.filter((_, j) => j !== i))}><Trash2 className="size-4" /></Button>
          </div>
        ))}
        <Button size="sm" variant="secondary" className="self-start" onClick={() => setRows([...rows, { [keyName]: '', weight: 0 }])}><Plus className="size-4" />{t('Add')}</Button>
      </div>
    </div>
  )
}

function TemplateEditor({ tpl, designations, onClose }: { tpl: any; designations: any[]; onClose: () => void }) {
  const { t } = useI18n()
  const qc = useQueryClient()
  const [d, setD] = useState<any>(tpl)
  const m = useMutation({ mutationFn: () => api.saveAppraisalTemplate(d), onSuccess: () => { qc.invalidateQueries({ queryKey: ['appraisal-setup'] }); onClose() } })
  return (
    <Modal open wide onClose={onClose} title={d.name ? d.title : t('New appraisal template')}
      footer={<><Button variant="secondary" onClick={onClose}>{t('Cancel')}</Button><Button loading={m.isPending} onClick={() => m.mutate()}>{t('Save')}</Button></>}>
      <div className="flex flex-col gap-4">
        <Field label={t('Title')}><Input value={d.title} disabled={!!d.name} onChange={(e) => setD({ ...d, title: e.target.value })} /></Field>
        <WeightRows label={t('Goals (KRAs)')} keyName="kra" rows={d.goals} setRows={(goals) => setD({ ...d, goals })} />
        <WeightRows label={t('Rating criteria (competencies)')} keyName="criteria" rows={d.criteria} setRows={(criteria) => setD({ ...d, criteria })} />
        <Field label={t('Use for designations')} hint={t('Employees with these designations get this template automatically.')}>
          <div className="flex max-h-40 flex-wrap gap-2 overflow-y-auto">
            {designations.map((x: any) => (
              <label key={x.name} className="flex items-center gap-1.5 text-sm">
                <input type="checkbox" className="size-4 accent-[var(--color-brand)]" checked={(d.designations ?? []).includes(x.name)}
                  onChange={(e) => setD({ ...d, designations: e.target.checked ? [...(d.designations ?? []), x.name] : (d.designations ?? []).filter((n: string) => n !== x.name) })} />
                {x.name}
              </label>
            ))}
          </div>
        </Field>
        {m.error && <ErrorBox error={m.error} />}
      </div>
    </Modal>
  )
}

function NewCycle({ setup, onClose, onStarted }: { setup: any; onClose: () => void; onStarted: (name: string) => void }) {
  const { t } = useI18n()
  const year = new Date().getFullYear()
  const [d, setD] = useState<any>({ cycle_name: `${t('Annual appraisal')} ${year}`, company: setup.companies[0] ?? '', start_date: `${year}-01-01`,
    end_date: `${year}-12-31`, department: '', branch: '', template: setup.templates[0]?.name ?? '' })
  const set = (k: string, v: unknown) => { preview.reset(); setD({ ...d, [k]: v }) }
  const preview = useMutation({ mutationFn: () => api.previewAppraisalCycle(d) })
  const start = useMutation({ mutationFn: () => api.startAppraisalCycle(d), onSuccess: (r: any) => onStarted(r.name) })
  return (
    <Modal open wide onClose={onClose} title={t('Start an appraisal cycle')}
      footer={<><Button variant="secondary" onClick={onClose}>{t('Cancel')}</Button>
        <Button variant="secondary" loading={preview.isPending} onClick={() => preview.mutate()}>{t('Preview employees')}</Button>
        <Button loading={start.isPending} disabled={!preview.data || preview.data.missing_template > 0 || !preview.data.employees.length} onClick={() => start.mutate()}>{t('Start cycle')}</Button></>}>
      <div className="grid gap-3 sm:grid-cols-2">
        <Field label={t('Name')}><Input value={d.cycle_name} onChange={(e) => set('cycle_name', e.target.value)} /></Field>
        <Field label={t('Company')}><Select value={d.company} onChange={(e) => set('company', e.target.value)}>{setup.companies.map((c: string) => <option key={c}>{c}</option>)}</Select></Field>
        <Field label={t('From')}><Input type="date" value={d.start_date} onChange={(e) => set('start_date', e.target.value)} /></Field>
        <Field label={t('To')}><Input type="date" value={d.end_date} onChange={(e) => set('end_date', e.target.value)} /></Field>
        <Field label={t('Department')}><Select value={d.department} onChange={(e) => set('department', e.target.value)}><option value="">{t('All')}</option>{setup.departments.map((x: string) => <option key={x}>{x}</option>)}</Select></Field>
        <Field label={t('Branch')}><Select value={d.branch} onChange={(e) => set('branch', e.target.value)}><option value="">{t('All')}</option>{setup.branches.map((x: string) => <option key={x}>{x}</option>)}</Select></Field>
        <Field label={t('Default template')} hint={t('Used when the designation has no template of its own.')}>
          <Select value={d.template} onChange={(e) => set('template', e.target.value)}><option value="">—</option>{setup.templates.map((x: any) => <option key={x.name} value={x.name}>{x.title}</option>)}</Select>
        </Field>
      </div>
      {preview.data && (
        <div className="mt-4 text-sm">
          <p className="mb-2 font-medium">{preview.data.employees.length} {t('employees')}{preview.data.missing_template > 0 && <span className="ms-2 text-red-700">· {preview.data.missing_template} {t('without a template')}</span>}</p>
          <ul className="max-h-48 overflow-y-auto rounded-xl border border-line text-xs">
            {preview.data.employees.map((e: any) => <li key={e.name} className="flex justify-between border-b border-line px-3 py-1.5 last:border-0"><span>{e.employee_name} · {e.designation || '—'}</span><span className={e.template ? 'text-muted' : 'text-red-700'}>{e.template || t('No template')}</span></li>)}
          </ul>
        </div>
      )}
      {(preview.error || start.error) && <div className="mt-3"><ErrorBox error={preview.error || start.error} /></div>}
    </Modal>
  )
}

function CycleDetail({ name, onBack }: { name: string; onBack: () => void }) {
  const { t, lang } = useI18n()
  const qc = useQueryClient()
  const q = useQuery({ queryKey: ['appraisal-cycle', name], queryFn: () => api.appraisalCycle(name) })
  const [open, setOpen] = useState<string | null>(null)
  const refresh = () => { qc.invalidateQueries({ queryKey: ['appraisal-cycle'] }); qc.invalidateQueries({ queryKey: ['appraisal-cycles'] }) }
  const finAll = useMutation({ mutationFn: () => api.finaliseReviewed(name), onSuccess: refresh })
  const complete = useMutation({ mutationFn: () => api.completeAppraisalCycle(name), onSuccess: refresh })
  if (q.isLoading) return <Spinner />
  if (q.error) return <ErrorBox error={q.error} />
  const c = q.data
  return (
    <Card title={c.cycle_name} subtitle={`${fmtDate(c.start_date, lang)} → ${fmtDate(c.end_date, lang)} · ${t(c.status)}`}
      action={<div className="flex flex-wrap gap-2">
        <Button size="sm" variant="secondary" onClick={onBack}>{t('All cycles')}</Button>
        {c.status !== 'Completed' && <Button size="sm" variant="secondary" disabled={!c.counts.Reviewed} loading={finAll.isPending} onClick={() => finAll.mutate()}>{t('Finalise reviewed')} ({c.counts.Reviewed})</Button>}
        {c.status !== 'Completed' && <Button size="sm" loading={complete.isPending} onClick={() => complete.mutate()}>{t('Complete cycle')}</Button>}
      </div>}>
      <div className="mb-3 flex flex-wrap gap-2 text-sm">
        {Object.entries(c.counts).map(([k, v]) => <Badge key={k} tone={STAGE_TONE[k]}>{t(k)}: {v as number}</Badge>)}
        <span className="text-muted">{t('Average final score')}: {fmtNumber(c.average, lang, 2)}</span>
      </div>
      {(finAll.error || complete.error) && <ErrorBox error={finAll.error || complete.error} />}
      <Table head={[t('Employee'), t('Manager'), t('Self'), t('Manager'), t('Goals'), t('Final score'), t('Stage')]}>
        {c.rows.map((r: any) => (
          <tr key={r.name}>
            <td className="py-2"><button className="font-medium text-brand hover:underline" onClick={() => setOpen(r.name)}>{r.employee_name}</button><div className="text-xs text-muted">{r.designation}</div></td>
            <td className="text-sm">{r.manager_name ?? <span className="text-red-700">{t('No reporting manager')}</span>}</td>
            <td>{fmtNumber(r.self_score, lang, 1)}</td><td>{fmtNumber(r.avg_feedback_score, lang, 1)}</td><td>{fmtNumber(r.total_score, lang, 1)}</td>
            <td className="font-semibold">{fmtNumber(r.final_score, lang, 2)}</td>
            <td><Badge tone={STAGE_TONE[r.stage]}>{t(r.stage)}</Badge></td>
          </tr>
        ))}
      </Table>
      <AppraisalForm name={open} onClose={() => setOpen(null)} />
    </Card>
  )
}

function ManagementCard() {
  const { t } = useI18n()
  const qc = useQueryClient()
  const q = useQuery({ queryKey: ['management-users'], queryFn: api.managementUsers })
  const [pick, setPick] = useState('')
  const m = useMutation({ mutationFn: ({ user, on }: { user: string; on: number }) => api.setManagementUser(user, on), onSuccess: (d) => { qc.setQueryData(['management-users'], d); setPick('') } })
  return (
    <Card title={t('Management approvers')} subtitle={t('Approve requests that need management (e.g. appraisal requests) after HR. This is a role, not the reporting-manager chain.')}>
      <div className="mb-3 flex flex-wrap gap-2">
        {(q.data ?? []).map((u: any) => (
          <span key={u.user} className="flex items-center gap-1.5 rounded-full bg-surface px-3 py-1 text-sm">{u.employee || u.full_name}
            <button aria-label={t('Remove')} onClick={() => m.mutate({ user: u.user, on: 0 })}><X className="size-3.5" /></button></span>
        ))}
        {!q.data?.length && <span className="text-sm text-muted">{t('Nobody yet. Requests that need management wait until someone is added.')}</span>}
      </div>
      <div className="flex max-w-md gap-2">
        <div className="flex-1"><LinkInput doctype="Employee" value={pick} onChange={setPick} /></div>
        <Button variant="secondary" disabled={!pick} loading={m.isPending} onClick={() => m.mutate({ user: pick, on: 1 })}>{t('Add')}</Button>
      </div>
      {m.error && <ErrorBox error={m.error} />}
    </Card>
  )
}

export default function Appraisals() {
  const { t, lang } = useI18n()
  const [tab, setTab] = useState<'cycles' | 'templates' | 'approvers'>('cycles')
  const [cycle, setCycle] = useState<string | null>(null)
  const [newCycle, setNewCycle] = useState(false)
  const [tpl, setTpl] = useState<any | null>(null)
  const cycles = useQuery({ queryKey: ['appraisal-cycles'], queryFn: api.appraisalCycles })
  const setup = useQuery({ queryKey: ['appraisal-setup'], queryFn: api.appraisalSetup })
  return (
    <div className="flex flex-col gap-5">
      <PageHeader title={t('Appraisals')} subtitle={t('Performance cycles (self-appraisal, manager review, HR final) and appraisal requests approved by HR and management')}
        actions={<div className="flex gap-2">
          <Link to="/requests" className="rounded-xl border border-line px-3 py-2 text-sm font-medium hover:bg-surface">{t('Appraisal requests')}</Link>
          {setup.data?.can_edit && <Button onClick={() => setNewCycle(true)} disabled={!setup.data?.templates?.length}><Plus className="size-4" />{t('Start an appraisal cycle')}</Button>}
        </div>} />
      <div className="flex gap-1 rounded-xl bg-surface p-1 text-sm" role="tablist">
        {([['cycles', 'Cycles'], ['templates', 'Templates'], ['approvers', 'Management approvers']] as const).map(([k, l]) => (
          <button key={k} role="tab" aria-selected={tab === k} onClick={() => setTab(k)} className={clsx('rounded-lg px-3 py-1.5', tab === k ? 'bg-white font-medium shadow-sm' : 'text-muted')}>{t(l)}</button>
        ))}
      </div>
      {tab === 'cycles' && (cycle ? <CycleDetail name={cycle} onBack={() => setCycle(null)} /> : (
        <Card>
          {cycles.isLoading ? <Spinner /> : cycles.error ? <ErrorBox error={cycles.error} /> : !cycles.data?.cycles?.length
            ? <Empty title={t('No appraisal cycles yet')} icon={<Star />}>{setup.data?.templates?.length ? t('Start a cycle to send self-appraisals to employees.') : t('Create a template first (goals and rating criteria).')}</Empty> : (
            <Table head={[t('Appraisal cycle'), t('Period'), t('Appraisals'), t('Submitted'), t('Average score'), t('Status')]}>
              {cycles.data.cycles.map((c: any) => (
                <tr key={c.name}>
                  <td className="py-2"><button className="font-medium text-brand hover:underline" onClick={() => setCycle(c.name)}>{c.cycle_name || c.name}</button></td>
                  <td className="text-sm">{fmtDate(c.start_date, lang)} → {fmtDate(c.end_date, lang)}</td>
                  <td>{c.appraisals}</td><td>{c.submitted}</td><td>{fmtNumber(c.average, lang, 2)}</td><td><StatusBadge status={c.status} /></td>
                </tr>
              ))}
            </Table>
          )}
        </Card>
      ))}
      {tab === 'templates' && (
        <Card title={t('Appraisal templates')} action={setup.data?.can_edit && <Button size="sm" onClick={() => setTpl({ title: '', goals: [{ kra: '', weight: 100 }], criteria: [{ criteria: '', weight: 100 }], designations: [] })}><Plus className="size-4" />{t('New template')}</Button>}>
          {setup.isLoading ? <Spinner /> : setup.error ? <ErrorBox error={setup.error} /> : !setup.data.templates.length ? <p className="text-sm text-muted">{t('No templates yet.')}</p> : (
            <ul className="divide-y divide-line">
              {setup.data.templates.map((x: any) => (
                <li key={x.name} className="flex flex-wrap items-center justify-between gap-2 py-2.5">
                  <div><div className="font-medium">{x.title}</div>
                    <div className="text-xs text-muted">{x.goals.length} {t('goals')} · {x.criteria.length} {t('criteria')}{x.designations.length ? ` · ${x.designations.join(', ')}` : ''}</div></div>
                  {setup.data.can_edit && <Button size="sm" variant="secondary" onClick={() => setTpl(x)}>{t('Edit')}</Button>}
                </li>
              ))}
            </ul>
          )}
        </Card>
      )}
      {tab === 'approvers' && <ManagementCard />}
      {tpl && setup.data && <TemplateEditor tpl={tpl} designations={setup.data.designations} onClose={() => setTpl(null)} />}
      {newCycle && setup.data && <NewCycle setup={setup.data} onClose={() => setNewCycle(false)} onStarted={(n) => { setNewCycle(false); setTab('cycles'); setCycle(n); cycles.refetch() }} />}
    </div>
  )
}
