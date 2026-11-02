import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Gavel, Plus } from 'lucide-react'
import { useEffect, useState } from 'react'
import { ActivityDrawer } from '../components/ActivityDrawer'
import { LinkInput } from '../components/LinkInput'
import { Badge, Button, Card, Empty, ErrorBox, Field, Input, Modal, PageHeader, Select, Spinner, StatusBadge, Table, Textarea } from '../components/ui'
import { api } from '../lib/api'
import { fmtDate, fmtMoney, monthStart, shiftMonth, todayISO } from '../lib/format'
import { useI18n } from '../lib/i18n'

export function stepText(s: any, t: (x: string) => string) {
  if (!s) return ''
  if (s.action === 'Deduction' || s.action === 'Suspension')
    return `${t(s.action)} ${s.days ? `${s.days} ${t('days')}` : ''}${s.days && s.percent ? ' + ' : ''}${s.percent ? `${s.percent}%` : ''}`.trim()
  return t(s.action)
}

function vtTitle(v: any, lang: string) { return lang === 'ar' && v?.title_ar ? v.title_ar : v?.title ?? '' }

function NewPenalty({ open, onClose, seed }: { open: boolean; onClose: () => void; seed?: any }) {
  const { t, lang } = useI18n()
  const qc = useQueryClient()
  const vts = useQuery({ queryKey: ['violation-types'], queryFn: () => api.violationTypes() })
  const [form, setForm] = useState<any>({})
  useEffect(() => {
    if (open) setForm(seed ? { employee: seed.employee, violation_type: seed.violation_type, violation_date: seed.date, source_ref: seed.source_ref,
      description: seed.minutes ? `${t(seed.source)}: ${seed.minutes} ${t('minutes')}` : t(seed.source) } : { violation_date: todayISO() })
  }, [open, seed, t])
  const ready = form.employee && form.violation_type && form.violation_date
  const pv = useQuery({ queryKey: ['penalty-preview', form.employee, form.violation_type, form.violation_date], enabled: open && !!ready,
    queryFn: () => api.penaltyPreview({ employee: form.employee, violation_type: form.violation_type, violation_date: form.violation_date }) })
  const m = useMutation({
    mutationFn: (issue: number) => api.createPenalty({ ...form, issue }),
    onSuccess: () => { onClose(); qc.invalidateQueries({ queryKey: ['penalties'] }); qc.invalidateQueries({ queryKey: ['penalty-suggestions'] }) },
  })
  const set = (k: string, v: any) => setForm((s: any) => ({ ...s, [k]: v }))
  return (
    <Modal open={open} onClose={onClose} title={t('New penalty')}
      footer={<>
        <Button variant="secondary" onClick={onClose}>{t('Cancel')}</Button>
        <Button variant="secondary" disabled={!ready || !form.description} loading={m.isPending && m.variables === 0} onClick={() => m.mutate(0)}>{t('Save draft')}</Button>
        <Button disabled={!ready || !form.description} loading={m.isPending && m.variables === 1} onClick={() => m.mutate(1)}>{t('Issue')}</Button>
      </>}>
      <div className="grid gap-4">
        <Field label={t('Employee')}><LinkInput doctype="Employee" value={form.employee ?? ''} onChange={(v) => set('employee', v)} /></Field>
        <Field label={t('Violation')}>
          <Select value={form.violation_type ?? ''} onChange={(e) => set('violation_type', e.target.value)}>
            <option value="">—</option>
            {(vts.data ?? []).map((v: any) => <option key={v.name} value={v.name}>{vtTitle(v, lang)}</option>)}
          </Select>
        </Field>
        <div className="grid grid-cols-2 gap-3">
          <Field label={t('Violation date')}><Input type="date" value={form.violation_date ?? ''} onChange={(e) => set('violation_date', e.target.value)} /></Field>
          <Field label={t('Discovered on')}><Input type="date" value={form.discovered_on ?? ''} onChange={(e) => set('discovered_on', e.target.value)} /></Field>
        </div>
        <Field label={t('Description')}><Textarea value={form.description ?? ''} onChange={(e) => set('description', e.target.value)} /></Field>
        {pv.isFetching ? <Spinner /> : pv.error ? <ErrorBox error={pv.error} /> : pv.data && (
          <div className="rounded-xl bg-surface p-3 text-sm">
            <div><b>{t('Occurrence')}:</b> {pv.data.occurrence} · <b>{t('Penalty')}:</b> {stepText(pv.data, t)}</div>
            {pv.data.amount > 0 && <div><b>{t('Deduction')}:</b> {fmtMoney(pv.data.amount, lang)} ({t('Daily wage')} {fmtMoney(pv.data.daily_wage, lang)})</div>}
            {pv.data.capped_note && <div className="text-amber-800">{pv.data.capped_note}</div>}
          </div>
        )}
        {m.error && <ErrorBox error={m.error} />}
      </div>
    </Modal>
  )
}

function Schedule() {
  const { t, lang } = useI18n()
  const qc = useQueryClient()
  const q = useQuery({ queryKey: ['violation-types', 'all'], queryFn: () => api.violationTypes(1) })
  const [edit, setEdit] = useState<any>(null)
  const [steps, setSteps] = useState('')
  const m = useMutation({ mutationFn: (d: any) => api.saveViolationType(d.name, d.data),
    onSuccess: () => { setEdit(null); qc.invalidateQueries({ queryKey: ['violation-types'] }) } })
  if (q.isLoading) return <Spinner />
  if (q.error) return <ErrorBox error={q.error} />
  const max = Math.max(4, ...q.data!.map((v: any) => v.steps.length))
  return (
    <Card title={t('Violations schedule')} subtitle={t('The penalty grows each time the same violation repeats within 180 days. Review against your approved work regulations.')}>
      <Table head={[t('Violation'), t('Category'), ...Array.from({ length: max }, (_, i) => `${t('Occurrence')} ${i + 1}`), t('Enabled'), '']}>
        {q.data!.map((v: any) => (
          <tr key={v.name}>
            <td className="py-2 font-medium">{vtTitle(v, lang)}</td>
            <td>{t(v.category)}</td>
            {Array.from({ length: max }, (_, i) => <td key={i} className="text-sm">{stepText(v.steps[i], t)}</td>)}
            <td><input type="checkbox" checked={!!v.enabled} onChange={() => m.mutate({ name: v.name, data: { enabled: v.enabled ? 0 : 1 } })} aria-label="enabled" /></td>
            <td><Button size="sm" variant="secondary" onClick={() => { setEdit(v); setSteps(JSON.stringify(v.steps, null, 2)) }}>{t('Edit')}</Button></td>
          </tr>
        ))}
      </Table>
      <Modal open={!!edit} onClose={() => setEdit(null)} wide title={edit ? vtTitle(edit, lang) : ''}
        footer={<><Button variant="secondary" onClick={() => setEdit(null)}>{t('Cancel')}</Button>
          <Button loading={m.isPending} onClick={() => { try { m.mutate({ name: edit.name, data: { steps: JSON.parse(steps) } }) } catch { alert(t('The field list is not valid JSON.')) } }}>{t('Save')}</Button></>}>
        <p className="mb-2 text-sm text-muted">{t('One entry per occurrence: action (Warning, Deduction, Suspension, Termination) with a percent of the daily wage, or days.')}</p>
        <Textarea rows={12} className="font-mono text-xs" value={steps} onChange={(e) => setSteps(e.target.value)} />
        {m.error && <ErrorBox error={m.error} />}
      </Modal>
    </Card>
  )
}

export default function Penalties() {
  const { t, lang } = useI18n()
  const qc = useQueryClient()
  const [tab, setTab] = useState<'list' | 'suggest' | 'schedule'>('list')
  const [month, setMonth] = useState(monthStart(todayISO()))
  const [status, setStatus] = useState('')
  const [open, setOpen] = useState(false)
  const [seed, setSeed] = useState<any>(null)
  const [trail, setTrail] = useState<string | null>(null)
  const [cancel, setCancel] = useState<any>(null)
  const [reason, setReason] = useState('')
  const q = useQuery({ queryKey: ['penalties', month, status], queryFn: () => api.penalties({ month, status }), enabled: tab === 'list' })
  const sug = useQuery({ queryKey: ['penalty-suggestions', month], queryFn: () => api.penaltySuggestions(month), enabled: tab === 'suggest' })
  const issue = useMutation({ mutationFn: api.issuePenalty, onSuccess: () => qc.invalidateQueries({ queryKey: ['penalties'] }) })
  const cm = useMutation({ mutationFn: () => api.cancelPenalty(cancel.name, reason),
    onSuccess: () => { setCancel(null); setReason(''); qc.invalidateQueries({ queryKey: ['penalties'] }) } })
  return (
    <div>
      <PageHeader title={t('Warnings & penalties')}
        actions={<div className="flex flex-wrap gap-2">
          <div className="flex rounded-xl border border-line p-0.5" role="tablist">
            {(['list', 'suggest', 'schedule'] as const).map((v) => (
              <button key={v} role="tab" aria-selected={tab === v} onClick={() => setTab(v)}
                className={`rounded-lg px-3 py-1.5 text-sm ${tab === v ? 'bg-brand text-white' : 'text-muted hover:bg-surface'}`}>
                {t(v === 'list' ? 'Penalties' : v === 'suggest' ? 'From attendance' : 'Violations schedule')}</button>
            ))}
          </div>
          <Button onClick={() => { setSeed(null); setOpen(true) }}><Plus className="size-4" />{t('New penalty')}</Button>
        </div>} />
      {tab !== 'schedule' && (
        <div className="mb-4 flex flex-wrap items-center gap-2">
          <Button size="sm" variant="secondary" onClick={() => setMonth(shiftMonth(month, -1))}>‹</Button>
          <Input type="month" className="w-44" value={month.slice(0, 7)} onChange={(e) => e.target.value && setMonth(e.target.value + '-01')} />
          <Button size="sm" variant="secondary" onClick={() => setMonth(shiftMonth(month, 1))}>›</Button>
          {tab === 'list' && (
            <Select className="w-44" value={status} onChange={(e) => setStatus(e.target.value)}>
              <option value="">{t('All')}</option>
              {['Draft', 'Issued', 'Acknowledged', 'Objected', 'Cancelled'].map((s) => <option key={s} value={s}>{t(s)}</option>)}
            </Select>
          )}
        </div>
      )}
      {tab === 'schedule' ? <Schedule /> : tab === 'suggest' ? (
        <Card subtitle={t('Late arrivals, early exits and absences of the month (last 30 days) that match a violation and have no penalty yet.')}>
          {sug.isLoading ? <Spinner /> : sug.error ? <ErrorBox error={sug.error} /> : !sug.data?.length ? <Empty title={t('Nothing to review')} icon={<Gavel />} /> : (
            <Table head={[t('Employee'), t('Date'), t('Issue'), t('Violation'), '']}>
              {sug.data.map((s: any) => (
                <tr key={s.source_ref}>
                  <td className="py-2">{s.employee_name}</td><td>{fmtDate(s.date, lang)}</td>
                  <td>{t(s.source)}{s.minutes ? ` · ${s.minutes} ${t('minutes')}` : ''}</td><td>{s.violation_type}</td>
                  <td><Button size="sm" onClick={() => { setSeed(s); setOpen(true) }}>{t('Review')}</Button></td>
                </tr>
              ))}
            </Table>
          )}
        </Card>
      ) : (
        <Card>
          {q.isLoading ? <Spinner /> : q.error ? <ErrorBox error={q.error} /> : !q.data?.length ? <Empty title={t('No penalties')} icon={<Gavel />} /> : (
            <Table head={[t('Employee'), t('Violation'), t('Date'), t('Occurrence'), t('Penalty'), t('Deduction'), t('Status'), '']}>
              {q.data.map((p: any) => (
                <tr key={p.name}>
                  <td className="py-2"><button className="text-start font-medium hover:underline" onClick={() => setTrail(p.name)}>{p.employee_name}</button></td>
                  <td className="text-sm">{p.violation_type}</td>
                  <td>{fmtDate(p.violation_date, lang)}</td>
                  <td>{p.occurrence}</td>
                  <td>{stepText(p, t)}</td>
                  <td>{p.amount ? fmtMoney(p.amount, lang) : '—'}{p.capped_note && <Badge tone="amber">{t('Capped')}</Badge>}</td>
                  <td><StatusBadge status={p.status} />{p.employee_reply && <div className="max-w-56 truncate text-xs text-muted" title={p.employee_reply}>“{p.employee_reply}”</div>}</td>
                  <td className="whitespace-nowrap">
                    {p.status === 'Draft' && <Button size="sm" loading={issue.isPending && issue.variables === p.name} onClick={() => issue.mutate(p.name)}>{t('Issue')}</Button>}
                    {p.status !== 'Cancelled' && <Button size="sm" variant="secondary" onClick={() => setCancel(p)}>{t('Cancel')}</Button>}
                  </td>
                </tr>
              ))}
            </Table>
          )}
          {issue.error && <ErrorBox error={issue.error} />}
        </Card>
      )}
      <NewPenalty open={open} seed={seed} onClose={() => setOpen(false)} />
      {trail && <ActivityDrawer doctype="AlphaX Penalty" name={trail} onClose={() => setTrail(null)} />}
      <Modal open={!!cancel} onClose={() => setCancel(null)} title={t('Cancel penalty')}
        footer={<><Button variant="secondary" onClick={() => setCancel(null)}>{t('Close')}</Button>
          <Button variant="danger" disabled={!reason.trim()} loading={cm.isPending} onClick={() => cm.mutate()}>{t('Cancel penalty')}</Button></>}>
        <p className="mb-2 text-sm text-muted">{t('Any payroll deduction is reversed.')}</p>
        <Textarea placeholder={t('Reason')} value={reason} onChange={(e) => setReason(e.target.value)} />
        {cm.error && <ErrorBox error={cm.error} />}
      </Modal>
    </div>
  )
}
