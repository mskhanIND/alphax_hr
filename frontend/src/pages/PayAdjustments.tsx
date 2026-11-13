import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import clsx from 'clsx'
import { AlertTriangle, Plus, TrendingUp, X } from 'lucide-react'
import { useState } from 'react'
import { LinkInput } from '../components/LinkInput'
import { Badge, Button, Card, ErrorBox, Field, Input, Modal, PageHeader, Select, Spinner, StatusBadge, Table, Textarea } from '../components/ui'
import { api } from '../lib/api'
import { fmtMoney, fmtMonth, monthStart, todayISO } from '../lib/format'
import { useI18n } from '../lib/i18n'

/** Employees picked from the list are added at once; one typed but not added still counts (see withPending). */
function People({ ids, setIds, department, setDepartment, pick, setPick }: { ids: string[]; setIds: (v: string[]) => void; department: string; setDepartment: (v: string) => void; pick: string; setPick: (v: string) => void }) {
  const { t } = useI18n()
  const add = (v: string) => { if (v && !ids.includes(v)) setIds([...ids, v]); setPick('') }
  return (
    <Field label={t('Employees')} hint={t('Add one or many, or a whole department.')}>
      <div className="flex flex-col gap-2">
        <div className="flex gap-2">
          <div className="flex-1"><LinkInput doctype="Employee" value={pick} onChange={setPick} onSelect={add} placeholder={t('Employee ID or name')} /></div>
          <Button size="sm" variant="secondary" disabled={!pick} onClick={() => add(pick)}><Plus className="size-4" />{t('Add')}</Button>
        </div>
        <div className="flex flex-wrap gap-1.5">
          {ids.map((e) => <span key={e} className="flex items-center gap-1 rounded-full bg-surface px-2.5 py-1 text-xs">{e}<button aria-label={t('Remove')} onClick={() => setIds(ids.filter((x) => x !== e))}><X className="size-3" /></button></span>)}
        </div>
        <LinkInput doctype="Department" value={department} onChange={setDepartment} placeholder={t('or a whole department')} />
      </div>
    </Field>
  )
}

function NewAdjustment({ meta, onClose }: { meta: any; onClose: () => void }) {
  const { t, lang } = useI18n()
  const qc = useQueryClient()
  const [d, setD] = useState<any>({ kind: 'Earning', category: 'Bonus', amount_type: 'Amount', amount: '', payroll_month: monthStart(todayISO()), reason: '', consent: 0, salary_component: '' })
  const [ids, setIds] = useState<string[]>([])
  const [pick, setPick] = useState('')
  const [department, setDepartment] = useState('')
  const set = (k: string, v: unknown) => { pv.reset(); setD({ ...d, [k]: v }) }
  const payload = { ...d, employees: pick && !ids.includes(pick) ? [...ids, pick] : ids, department: department || undefined }
  const pv = useMutation({ mutationFn: () => api.previewPayAdjustment(payload) })
  const m = useMutation({ mutationFn: () => api.createPayAdjustment(payload), onSuccess: () => { qc.invalidateQueries({ queryKey: ['pay-adjustments'] }); onClose() } })
  const cats: string[] = meta.categories[d.kind]
  const comps = meta.components.filter((c: any) => c.type === d.kind)
  const bad = (pv.data?.rows ?? []).some((r: any) => r.problems.length)
  return (
    <Modal open wide onClose={onClose} title={t('Bonus or deduction')}
      footer={<><Button variant="secondary" onClick={onClose}>{t('Cancel')}</Button>
        <Button variant="secondary" loading={pv.isPending} onClick={() => pv.mutate()}>{t('Check')}</Button>
        <Button disabled={!pv.data || bad} loading={m.isPending} onClick={() => m.mutate()}>{t('Post to payroll')}</Button></>}>
      <div className="grid gap-3 sm:grid-cols-2">
        <Field label={t('Kind')}>
          <div className="flex gap-1 rounded-xl bg-surface p-1 text-sm">
            {['Earning', 'Deduction'].map((k) => <button key={k} className={clsx('flex-1 rounded-lg px-3 py-1.5', d.kind === k ? 'bg-white font-medium shadow-sm' : 'text-muted')}
              onClick={() => { pv.reset(); setD({ ...d, kind: k, category: meta.categories[k][0], salary_component: '' }) }}>{t(k === 'Earning' ? 'Bonus / payment' : 'Deduction')}</button>)}
          </div>
        </Field>
        <Field label={t('Category')} hint={meta.guide[d.category]}>
          <Select value={d.category} onChange={(e) => set('category', e.target.value)}>{cats.map((c) => <option key={c} value={c}>{t(c)}</option>)}</Select>
        </Field>
        <Field label={t('Amount')}>
          <div className="flex gap-2">
            <Input type="number" min={0} value={d.amount} onChange={(e) => set('amount', e.target.value)} />
            <Select className="!w-36" value={d.amount_type} onChange={(e) => set('amount_type', e.target.value)}>
              <option value="Amount">SAR</option><option value="% of wage">{t('% of wage')}</option>
            </Select>
          </div>
        </Field>
        <Field label={t('Payroll month')}><Input type="month" value={d.payroll_month.slice(0, 7)} onChange={(e) => set('payroll_month', `${e.target.value}-01`)} /></Field>
        <Field label={t('Salary component')} hint={t('Blank: the default in Settings')}>
          <Select value={d.salary_component} onChange={(e) => set('salary_component', e.target.value)}><option value="">—</option>{comps.map((c: any) => <option key={c.name}>{c.name}</option>)}</Select>
        </Field>
        <People ids={ids} setIds={(v) => { pv.reset(); setIds(v) }} department={department} setDepartment={(v) => { pv.reset(); setDepartment(v) }} pick={pick} setPick={(v) => { pv.reset(); setPick(v) }} />
      </div>
      {d.kind === 'Deduction' && meta.needs_consent.includes(d.category) && (
        <label className="mt-3 flex items-center gap-2 text-sm"><input type="checkbox" className="size-4 accent-[var(--color-brand)]" checked={!!d.consent} onChange={(e) => set('consent', e.target.checked ? 1 : 0)} />
          {t('The employee agreed in writing (keep the signed copy on the employee file).')}</label>
      )}
      <Field label={t('Reason')}><Textarea rows={2} value={d.reason} onChange={(e) => set('reason', e.target.value)} /></Field>
      {pv.error && <ErrorBox error={pv.error} />}
      {pv.data && (
        <div className="mt-3 max-h-64 overflow-y-auto rounded-xl border border-line">
          {pv.data.rows.map((r: any) => (
            <div key={r.employee} className="border-b border-line px-3 py-2 text-sm last:border-0">
              <div className="flex justify-between"><span className="font-medium">{r.employee_name}</span><span>{fmtMoney(r.amount, lang)}</span></div>
              {r.lines.length > 1 && <div className="text-xs text-muted">{r.lines.map((l: any) => `${fmtMonth(l.month, lang)}: ${fmtMoney(l.amount, lang)}`).join(' · ')}</div>}
              {r.problems.map((p: string, i: number) => <div key={i} className="flex items-start gap-1 text-xs text-red-700"><AlertTriangle className="mt-0.5 size-3" />{p}</div>)}
            </div>
          ))}
        </div>
      )}
      {m.error && <div className="mt-3"><ErrorBox error={m.error} /></div>}
    </Modal>
  )
}

function Increment({ onClose }: { onClose: () => void }) {
  const { t, lang } = useI18n()
  const [d, setD] = useState<any>({ mode: 'percent_all', value: 5, from_date: monthStart(todayISO()), reason: '' })
  const [ids, setIds] = useState<string[]>([])
  const [pick, setPick] = useState('')
  const [department, setDepartment] = useState('')
  const payload = { ...d, employees: pick && !ids.includes(pick) ? [...ids, pick] : ids, department: department || undefined }
  const pv = useMutation({ mutationFn: () => api.salaryIncrement(payload, 0) })
  const m = useMutation({ mutationFn: () => api.salaryIncrement(payload, 1) })
  const set = (k: string, v: unknown) => { pv.reset(); setD({ ...d, [k]: v }) }
  const res = m.data ?? pv.data
  return (
    <Modal open wide onClose={onClose} title={t('Salary increment')}
      footer={<><Button variant="secondary" onClick={onClose}>{m.data ? t('Close') : t('Cancel')}</Button>
        {!m.data && <Button variant="secondary" loading={pv.isPending} onClick={() => pv.mutate()}>{t('Preview')}</Button>}
        {!m.data && <Button disabled={!pv.data} loading={m.isPending} onClick={() => m.mutate()}>{t('Apply increment')}</Button>}</>}>
      <div className="grid gap-3 sm:grid-cols-3">
        <Field label={t('How')}><Select value={d.mode} onChange={(e) => set('mode', e.target.value)}>
          <option value="percent_all">{t('% of the whole salary')}</option><option value="percent_basic">{t('% of basic')}</option><option value="amount_basic">{t('Amount added to basic')}</option></Select></Field>
        <Field label={t('Value')}><Input type="number" min={0} value={d.value} onChange={(e) => set('value', Number(e.target.value))} /></Field>
        <Field label={t('From')}><Input type="date" value={d.from_date} onChange={(e) => set('from_date', e.target.value)} /></Field>
      </div>
      <People ids={ids} setIds={(v) => { pv.reset(); setIds(v) }} department={department} setDepartment={(v) => { pv.reset(); setDepartment(v) }} pick={pick} setPick={(v) => { pv.reset(); setPick(v) }} />
      <Field label={t('Reason')}><Textarea rows={2} value={d.reason} onChange={(e) => set('reason', e.target.value)} /></Field>
      {(pv.error || m.error) && <ErrorBox error={pv.error || m.error} />}
      {res && (
        <Table head={[t('Employee'), t('Before'), t('After'), '']}>
          {res.rows.map((r: any) => (
            <tr key={r.employee}><td className="py-1.5">{r.employee_name}</td>
              <td>{r.before != null ? fmtMoney(r.before, lang) : '—'}</td><td className="font-semibold">{r.after != null ? fmtMoney(r.after, lang) : '—'}</td>
              <td className="text-xs">{r.skipped ? <span className="text-red-700">{r.skipped}</span> : r.assignment ? <Badge tone="green">{t('Applied')}</Badge> : null}</td></tr>
          ))}
        </Table>
      )}
    </Modal>
  )
}

function DeductionStatus() {
  const { t, lang } = useI18n()
  const [emp, setEmp] = useState('')
  const [month, setMonth] = useState(monthStart(todayISO()))
  const q = useQuery({ queryKey: ['deduction-status', emp, month], queryFn: () => api.deductionStatus(emp, month), enabled: !!emp, retry: false })
  const d = q.data
  return (
    <Card title={t('How much more can be deducted?')} subtitle={t('Before adding a deduction, pick the employee and month: AlphaX adds up everything already deducted (penalties, loans, damages, other deductions) and shows the room left. By law the total cannot pass half the wage (Art. 91–93); a loan instalment is at most 10% unless the employee agreed in writing, and damages at most 5 days\' wage a month.')}>
      <div className="grid gap-3 sm:grid-cols-2">
        <Field label={t('Employee')}><LinkInput doctype="Employee" value={emp} onChange={setEmp} /></Field>
        <Field label={t('Month')}><Input type="month" value={month.slice(0, 7)} onChange={(e) => setMonth(`${e.target.value}-01`)} /></Field>
      </div>
      {q.error && <ErrorBox error={q.error} />}
      {d && (
        <div className="mt-3 text-sm">
          <div className="mb-2 h-3 w-full overflow-hidden rounded-full bg-surface">
            <div className={clsx('h-full', d.total > d.half_wage ? 'bg-red-500' : 'bg-brand')} style={{ width: `${Math.min(100, (d.total / (d.half_wage || 1)) * 100)}%` }} />
          </div>
          <p>{t('Deducted')}: <b>{fmtMoney(d.total, lang)}</b> / {t('half the wage')} {fmtMoney(d.half_wage, lang)} · {t('room left')}: <b>{fmtMoney(d.room, lang)}</b></p>
          <ul className="mt-2 text-xs text-muted">{d.items.map((i: any) => <li key={i.kind}>{i.label}: {fmtMoney(i.amount, lang)}</li>)}</ul>
          <p className="mt-1 text-xs text-muted">{t('Loan cap (10%)')}: {fmtMoney(d.loan_cap, lang)} · {t('Damage cap (5 days)')}: {fmtMoney(d.damage_cap, lang)}</p>
          {d.problems.map((p: string, i: number) => <p key={i} className="text-xs text-red-700">{p}</p>)}
        </div>
      )}
    </Card>
  )
}

export default function PayAdjustments() {
  const { t, lang } = useI18n()
  const qc = useQueryClient()
  const [month, setMonth] = useState(monthStart(todayISO()))
  const q = useQuery({ queryKey: ['pay-adjustments', month], queryFn: () => api.payAdjustments(month) })
  const [add, setAdd] = useState(false)
  const [inc, setInc] = useState(false)
  const cancel = useMutation({ mutationFn: (name: string) => api.cancelPayAdjustment(name), onSuccess: () => qc.invalidateQueries({ queryKey: ['pay-adjustments'] }) })
  return (
    <div className="flex flex-col gap-5">
      <PageHeader title={t('Bonuses & deductions')} subtitle={t('One-time payments, HR deductions and salary increments - single or bulk')}
        actions={<div className="flex gap-2">
          <Button variant="secondary" onClick={() => setInc(true)}><TrendingUp className="size-4" />{t('Salary increment')}</Button>
          <Button onClick={() => setAdd(true)} disabled={!q.data}><Plus className="size-4" />{t('Bonus or deduction')}</Button></div>} />
      <Card title={fmtMonth(month, lang)} action={<Input type="month" className="!w-40" value={month.slice(0, 7)} onChange={(e) => setMonth(`${e.target.value}-01`)} />}>
        {q.isLoading ? <Spinner /> : q.error ? <ErrorBox error={q.error} /> : !q.data.rows.length ? <p className="text-sm text-muted">{t('Nothing for this month yet.')}</p> : (
          <Table head={[t('Employee'), t('Category'), t('Amount'), t('Reason'), t('Status'), '']}>
            {q.data.rows.map((r: any) => (
              <tr key={r.name}>
                <td className="py-2 font-medium">{r.employee_name}<div className="text-xs text-muted">{r.name}{r.batch ? ` · ${t('batch')} ${r.batch}` : ''}</div></td>
                <td><Badge tone={r.kind === 'Earning' ? 'green' : 'red'}>{t(r.category)}</Badge></td>
                <td>{fmtMoney(r.amount, lang)}{r.lines.length > 1 && <div className="text-xs text-muted">{r.lines.length} {t('months')}</div>}</td>
                <td className="max-w-xs truncate text-sm text-muted">{r.reason}</td>
                <td><StatusBadge status={r.status} /></td>
                <td>{r.status === 'Posted' && <Button size="sm" variant="ghost" loading={cancel.isPending && cancel.variables === r.name} onClick={() => cancel.mutate(r.name)}>{t('Cancel')}</Button>}</td>
              </tr>
            ))}
          </Table>
        )}
        {cancel.error && <ErrorBox error={cancel.error} />}
      </Card>
      <DeductionStatus />
      {add && q.data && <NewAdjustment meta={q.data} onClose={() => setAdd(false)} />}
      {inc && <Increment onClose={() => setInc(false)} />}
    </div>
  )
}
