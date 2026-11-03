import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { AlertTriangle } from 'lucide-react'
import { useEffect, useState } from 'react'
import { Badge, Button, Card, ErrorBox, Field, Input, PageHeader, Spinner } from '../components/ui'
import { api } from '../lib/api'
import { fmtDate, fmtNumber } from '../lib/format'
import { useI18n } from '../lib/i18n'
import LeaveCountingCard from '../components/LeaveCountingCard'

const KIND_LABEL: Record<string, string> = {
  annual: 'Annual leave', sick: 'Sick leave', maternity: 'Maternity', paternity: 'Paternity', marriage: 'Marriage',
  bereavement: 'Bereavement', bereavement_sibling: 'Bereavement (sibling)', iddah_muslim: 'Iddah (Muslim)',
  iddah_other: 'Iddah (non-Muslim)', exam: 'Examination', hajj: 'Hajj',
}

function RuleRow({ r, canEdit, onSaved }: { r: any; canEdit: boolean; onSaved: (d: any) => void }) {
  const { t } = useI18n()
  const [maxDays, setMaxDays] = useState<string>(r.max_days ?? '')
  useEffect(() => setMaxDays(r.max_days ?? ''), [r.max_days])
  const save = useMutation({ mutationFn: (data: Record<string, unknown>) => api.updateLeaveRule(r.name, data), onSuccess: onSaved })
  const allow = useMutation({ mutationFn: () => api.allowWithoutAllocation(r.leave_type), onSuccess: onSaved })
  return (
    <tr className="align-top">
      <td className="py-2.5 pe-3">
        <div className="font-medium">{r.leave_type}</div>
        <div className="text-xs text-muted">{t(KIND_LABEL[r.rule] ?? r.rule)}</div>
        {!r.exists && <Badge tone="red">{t('Leave type missing')}</Badge>}
        {r.needs_allocation && r.rule !== 'annual' && (
          <div className="mt-1 flex flex-wrap items-center gap-2 text-xs text-amber-800">
            <AlertTriangle className="size-3.5" />{t('Needs an allocation before employees can apply')}
            {canEdit && <Button size="sm" variant="secondary" loading={allow.isPending} onClick={() => allow.mutate()}>{t('Allow without allocation')}</Button>}
          </div>
        )}
        {(save.error || allow.error) && <ErrorBox error={save.error || allow.error} />}
      </td>
      <td className="py-2.5 pe-3">
        {r.rule === 'Sick' ? <span className="text-xs text-muted">{t('120 days per sick-leave year (Art. 117)')}</span> :
        <Input type="number" min={0} step="1" className="!w-24" placeholder={t('No limit')} value={maxDays} disabled={!canEdit}
          onChange={(e) => setMaxDays(e.target.value)}
          onBlur={() => String(maxDays) !== String(r.max_days ?? '') && save.mutate({ max_days: maxDays === '' ? null : Number(maxDays) })} />}
      </td>
      <td className="py-2.5 pe-3 text-xs text-muted">
        {[r.gender && t(r.gender), r.lifetime_limit && `${r.lifetime_limit}× ${t('per employment')}`,
          r.min_service_days && `${t('after')} ${r.min_service_days} ${t('days of service')}`,
          r.requires_event_date && (r.event_label ? t(r.event_label) : t('Event date'))].filter(Boolean).join(' · ') || '—'}
      </td>
      <td className="py-2.5 pe-3">
        <input type="checkbox" className="size-4 accent-[var(--color-brand)]" checked={!!r.requires_attachment} disabled={!canEdit}
          aria-label={t('Document required')} onChange={(e) => save.mutate({ requires_attachment: e.target.checked ? 1 : 0 })} />
      </td>
      <td className="py-2.5">
        <input type="checkbox" className="size-4 accent-[var(--color-brand)]" checked={!!r.enabled} disabled={!canEdit}
          aria-label={t('Enabled')} onChange={(e) => save.mutate({ enabled: e.target.checked ? 1 : 0 })} />
      </td>
    </tr>
  )
}

const POLICY_LAW = 'Saudi Labor Law'
const POLICY_FIXED = 'Fixed for all employees'
const SOURCE_LABEL: Record<string, string> = { contract: 'Contract', company: 'Company policy', law: 'Labor Law', legal_minimum: 'Legal minimum' }

function AnnualCard({ annual, canEdit, onSaved }: { annual: any; canEdit: boolean; onSaved: (d: any) => void }) {
  const { t, lang } = useI18n()
  const [form, setForm] = useState(annual)
  useEffect(() => setForm(annual), [annual])
  const qc = useQueryClient()
  const plan = useQuery<any>({ queryKey: ['annualPlan'], queryFn: () => api.annualAllocation(0) })
  const refresh = (d: any) => { onSaved(d); qc.invalidateQueries({ queryKey: ['annualPlan'] }) }
  const save = useMutation({
    mutationFn: () => api.updateAnnualSettings({
      annual_policy: form.annual_policy, annual_fixed_days: form.annual_fixed_days, annual_auto_allocate: form.annual_auto_allocate,
      annual_base_days: form.annual_base_days, annual_senior_days: form.annual_senior_days, annual_senior_after_years: form.annual_senior_after_years,
      annual_senior_count_from: form.annual_senior_count_from || null,
    }),
    onSuccess: refresh,
  })
  const setupType = useMutation({ mutationFn: api.setupAnnualLeaveType, onSuccess: refresh })
  const apply = useMutation({ mutationFn: () => api.annualAllocation(1), onSuccess: (d) => qc.setQueryData(['annualPlan'], d) })
  const num = (k: string) => (
    <Input type="number" min={21} value={form[k] ?? ''} disabled={!canEdit} onChange={(e) => setForm({ ...form, [k]: e.target.value })} />
  )
  const fixed = form.annual_policy === POLICY_FIXED
  const p = plan.data
  return (
    <Card title={t('Annual leave (Art. 109)')} subtitle={t('Allocated per service year, from each employee\'s joining anniversary.')}>
      <div className="flex flex-wrap items-center gap-3 rounded-xl bg-surface p-3">
        <span className="text-sm text-muted">{t('Leave type')}</span>
        {annual.annual_leave_type ? (
          <span className="font-semibold">{annual.annual_leave_type} <span className="ms-1 text-xs font-normal text-muted">🔒 {t('fixed name')}</span></span>
        ) : canEdit ? (
          <Button size="sm" loading={setupType.isPending} onClick={() => setupType.mutate()}>{t('Set up Annual Leave')}</Button>
        ) : <span className="text-sm text-amber-800">{t('Not set up yet')}</span>}
      </div>
      {setupType.error && <ErrorBox error={setupType.error} />}

      <div className="mt-4">
        <div className="mb-2 text-sm font-medium">{t('Company policy')}</div>
        <div className="flex flex-col gap-2 sm:flex-row">
          {[POLICY_LAW, POLICY_FIXED].map((pol) => (
            <label key={pol} className={`flex flex-1 cursor-pointer items-start gap-2 rounded-xl border p-3 text-sm ${form.annual_policy === pol ? 'border-brand bg-brand-50' : 'border-line'}`}>
              <input type="radio" name="annual_policy" className="mt-0.5 accent-[var(--color-brand)]" checked={form.annual_policy === pol} disabled={!canEdit}
                onChange={() => setForm({ ...form, annual_policy: pol })} />
              <span><span className="font-medium">{t(pol)}</span><br />
                <span className="text-muted">{pol === POLICY_LAW ? t('21 days, 30 days after 5 years of service') : t('The same days for every employee, e.g. 30')}</span></span>
            </label>
          ))}
        </div>
        <div className="mt-3 grid gap-3 sm:grid-cols-4">
          {fixed ? <Field label={t('Days per year')}>{num('annual_fixed_days')}</Field> : (<>
            <Field label={t('Days per year')}>{num('annual_base_days')}</Field>
            <Field label={t('Senior days per year')}>{num('annual_senior_days')}</Field>
            <Field label={t('Senior after (years)')}><Input type="number" min={1} value={form.annual_senior_after_years ?? ''} disabled={!canEdit}
              onChange={(e) => setForm({ ...form, annual_senior_after_years: e.target.value })} /></Field>
            <Field label={t('Count seniority from')} hint={t('Optional. Blank = from each joining date.')}>
              <Input type="date" value={form.annual_senior_count_from ?? ''} disabled={!canEdit}
                onChange={(e) => setForm({ ...form, annual_senior_count_from: e.target.value })} /></Field>
          </>)}
        </div>
        <p className="mt-2 text-xs text-muted">
          {t('An employee\'s contract days (Profile → Saudi compliance) override the company policy.')}{' '}
          {annual.contract_overrides > 0 && <span className="font-medium text-ink">{annual.contract_overrides} {t('employees have contract days.')}</span>}{' '}
          {t('The legal minimum always applies.')}
        </p>
      </div>
      <label className="mt-3 flex items-center gap-2 text-sm">
        <input type="checkbox" className="size-4 accent-[var(--color-brand)]" checked={!!Number(form.annual_auto_allocate)} disabled={!canEdit}
          onChange={(e) => setForm({ ...form, annual_auto_allocate: e.target.checked ? 1 : 0 })} />
        {t('Allocate automatically every night')}
      </label>
      {canEdit && <div className="mt-3"><Button variant="secondary" loading={save.isPending} onClick={() => save.mutate()}>{t('Save')}</Button></div>}
      {save.error && <ErrorBox error={save.error} />}

      <div className="mt-5 border-t border-line pt-4">
        {plan.isLoading ? <Spinner /> : plan.error ? <ErrorBox error={plan.error} /> : !p?.configured ? (
          <p className="text-sm text-muted">{t('Set up the annual leave type to see the allocation plan.')}</p>
        ) : (
          <>
            <div className="flex flex-wrap items-center gap-3 text-sm">
              <span className="font-medium">{t('Allocation plan')} · {fmtDate(p.on, lang)}</span>
              <Badge tone="green">{t('to create')}: {p.counts.create}</Badge>
              <Badge>{t('already allocated')}: {p.counts.exists}</Badge>
              {p.counts.conflict > 0 && <Badge tone="amber">{t('overlapping allocation')}: {p.counts.conflict}</Badge>}
              {canEdit && p.counts.create > 0 && <Button size="sm" loading={apply.isPending} onClick={() => apply.mutate()}>{t('Create allocations')}</Button>}
            </div>
            {apply.error && <ErrorBox error={apply.error} />}
            <div className="mt-3 max-h-80 overflow-auto">
              <table className="w-full text-sm">
                <thead className="text-start text-xs text-muted"><tr>
                  <th className="pb-2 text-start">{t('Employee')}</th><th className="pb-2 text-start">{t('Service year')}</th>
                  <th className="pb-2 text-start">{t('Period')}</th><th className="pb-2 text-start">{t('Days')}</th>
                  <th className="pb-2 text-start">{t('Based on')}</th><th className="pb-2 text-start">{t('Status')}</th>
                </tr></thead>
                <tbody className="divide-y divide-line">
                  {p.rows.map((r: any) => (
                    <tr key={r.employee}>
                      <td className="py-1.5">{r.employee_name}</td>
                      <td className="py-1.5 tabular-nums">{r.service_year}</td>
                      <td className="py-1.5">{fmtDate(r.from_date, lang)} → {fmtDate(r.to_date, lang)}</td>
                      <td className="py-1.5 tabular-nums">{fmtNumber(r.days, lang)}</td>
                      <td className="py-1.5 text-xs text-muted">{t(SOURCE_LABEL[r.source] ?? r.source ?? '')}</td>
                      <td className="py-1.5"><Badge tone={r.action === 'create' ? 'green' : r.action === 'conflict' ? 'amber' : 'gray'}>
                        {t(r.action === 'create' ? 'to create' : r.action === 'conflict' ? 'overlapping allocation' : 'already allocated')}</Badge></td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </>
        )}
      </div>
    </Card>
  )
}

function EscalationCard({ hours, remind, canEdit, onSaved }: { hours: number; remind: number; canEdit: boolean; onSaved: (d: any) => void }) {
  const { t } = useI18n()
  const [v, setV] = useState<string>(String(hours ?? 0))
  const [r, setR] = useState<string>(String(remind ?? 0))
  useEffect(() => setV(String(hours ?? 0)), [hours])
  useEffect(() => setR(String(remind ?? 0)), [remind])
  const save = useMutation({ mutationFn: () => api.updateAnnualSettings({ leave_escalation_hours: Number(v) || 0, approval_remind_hours: Number(r) || 0 }), onSuccess: onSaved })
  return (
    <Card title={t('Approval delays')} subtitle={t('Remind the approver, then escalate to their manager and HR, when any request is left waiting.')}>
      <div className="flex flex-wrap items-end gap-3">
        <Field label={t('Remind approver after (hours)')} hint={t('0 = off')}>
          <Input type="number" min={0} className="!w-32" value={r} disabled={!canEdit} onChange={(e) => setR(e.target.value)} />
        </Field>
        <Field label={t('Escalate after (hours)')} hint={t('0 = off')}>
          <Input type="number" min={0} className="!w-32" value={v} disabled={!canEdit} onChange={(e) => setV(e.target.value)} />
        </Field>
        {canEdit && <Button variant="secondary" loading={save.isPending} onClick={() => save.mutate()}>{t('Save')}</Button>}
      </div>
      {save.error && <ErrorBox error={save.error} />}
    </Card>
  )
}

export default function LeaveSetup() {
  const { t } = useI18n()
  const qc = useQueryClient()
  const q = useQuery<any>({ queryKey: ['leaveSetup'], queryFn: api.leaveSetup })
  const onSaved = (d: any) => { if (d?.rules) qc.setQueryData(['leaveSetup'], d); qc.invalidateQueries({ queryKey: ['leaveTypes'] }) }
  const create = useMutation({ mutationFn: api.createStatutoryLeaveTypes, onSuccess: onSaved })
  if (q.isLoading) return <Spinner />
  if (q.error) return <ErrorBox error={q.error} onRetry={() => q.refetch()} />
  const d = q.data
  return (
    <div className="flex flex-col gap-5">
      <PageHeader title={t('Leave setup')} subtitle={t('Saudi Labor Law leave rules, checked on every leave request.')} />
      <AnnualCard annual={d.annual} canEdit={d.can_edit} onSaved={onSaved} />
      <Card title={t('Sick and statutory leave')}
        action={d.can_edit && d.missing_kinds.length > 0 ? (
          <Button size="sm" loading={create.isPending} onClick={() => create.mutate()}>{t('Create statutory leave types')} ({d.missing_kinds.length})</Button>
        ) : undefined}>
        {create.error && <ErrorBox error={create.error} />}
        {create.data?.created?.length > 0 && <p className="mb-2 text-sm text-emerald-700">{t('Created')}: {create.data.created.join(', ')}</p>}
        {d.missing_kinds.length > 0 && (
          <p className="mb-3 text-sm text-muted">{t('Not set up yet')}: {d.missing_kinds.map((k: string) => t(KIND_LABEL[k] ?? k)).join(' · ')}</p>
        )}
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead className="text-xs text-muted"><tr>
              <th className="pb-2 text-start">{t('Leave type')}</th><th className="pb-2 text-start">{t('Max days')}</th>
              <th className="pb-2 text-start">{t('Conditions')}</th><th className="pb-2 text-start">{t('Document required')}</th><th className="pb-2 text-start">{t('Enabled')}</th>
            </tr></thead>
            <tbody className="divide-y divide-line">
              {d.rules.map((r: any) => <RuleRow key={r.name} r={r} canEdit={d.can_edit} onSaved={onSaved} />)}
            </tbody>
          </table>
        </div>
      </Card>
      <LeaveCountingCard />
      <EscalationCard hours={d.annual.leave_escalation_hours} remind={d.annual.approval_remind_hours} canEdit={d.can_edit} onSaved={onSaved} />
    </div>
  )
}
