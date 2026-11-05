import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { ArrowDown, ArrowUp, GitBranch, Pencil, Plus, Trash2 } from 'lucide-react'
import { useState } from 'react'
import { LinkInput } from '../components/LinkInput'
import { Badge, Button, Card, Empty, ErrorBox, Field, Input, Modal, PageHeader, Select, Spinner, Textarea } from '../components/ui'
import { api } from '../lib/api'
import { useI18n } from '../lib/i18n'

const BLANK = {
  policy_name: '', enabled: 1, applies_to: 'All approvals', priority: 0, description: '', request_type: '', leave_type: '', company: '',
  department: '', branch: '', designation: '', min_amount: 0, min_days: 0, escalate_after_days: 2, remind_after_days: 1, auto_reject: 1,
  reject_after_days: 2, rejection_comment: '', multi_level: 0, restart_rule: 'From the first level', skip_repeat: 1, levels: [] as any[],
}
const NO_AUTO = ['Attendance corrections', 'Compensatory leave']

/** The timeline in words: 2 days → HR · +1 day reminder · +2 days rejected. */
function Timeline({ p }: { p: any }) {
  const { t } = useI18n()
  const steps: [string, number | null, string][] = []
  if (Number(p.escalate_after_days)) steps.push([t('Escalated to HR'), Number(p.escalate_after_days), 'amber'])
  if (Number(p.remind_after_days)) steps.push([t('HR reminds the approver'), Number(p.remind_after_days), 'amber'])
  if (Number(p.auto_reject) && !NO_AUTO.includes(p.applies_to)) steps.push([t('Rejected automatically'), Number(p.reject_after_days), 'red'])
  if (!steps.length) return <span className="text-sm text-muted">{t('No waiting times')}</span>
  return (
    <ol className="flex flex-wrap items-center gap-1.5 text-xs">
      <li><Badge tone="blue">{t('Submitted')}</Badge></li>
      {steps.map(([label, days, tone], i) => (
        <li key={i} className="flex items-center gap-1.5">
          <span className="text-muted">— {days} {t('working days')} →</span><Badge tone={tone}>{label}</Badge>
        </li>
      ))}
    </ol>
  )
}

function Levels({ p }: { p: any }) {
  const { t } = useI18n()
  if (!Number(p.multi_level) || !p.levels?.length) return null
  return (
    <div className="flex flex-wrap items-center gap-1.5 text-xs">
      <GitBranch className="size-4 text-muted" />
      {p.levels.map((l: any, i: number) => (
        <span key={i} className="flex items-center gap-1.5">
          {i > 0 && <span className="text-muted">→</span>}
          <span className="rounded-full bg-brand-50 px-2 py-0.5 text-brand">
            {l.level_label || t(l.approver_type)}{l.approver_type === 'Specific user' && l.user ? ` (${l.user})` : ''}
            {Number(l.min_amount) ? ` · ≥ ${Number(l.min_amount).toLocaleString()}` : ''}{Number(l.min_days) ? ` · ≥ ${l.min_days} ${t('days')}` : ''}
          </span>
        </span>
      ))}
      <span className="text-muted">· {t('After a rejection')}: {t(p.restart_rule)}</span>
    </div>
  )
}

function PolicyForm({ policy, meta, onClose }: { policy: any | null; meta: any; onClose: () => void }) {
  const { t } = useI18n()
  const qc = useQueryClient()
  const [v, setV] = useState<any>(() => policy ? { ...BLANK, ...policy, levels: policy.levels.map((l: any) => ({ ...l })) }
    : { ...BLANK, rejection_comment: meta.default_comment })
  const set = (k: string, x: any) => setV((s: any) => ({ ...s, [k]: x }))
  const setLevel = (i: number, k: string, x: any) => setV((s: any) => ({ ...s, levels: s.levels.map((l: any, j: number) => j === i ? { ...l, [k]: x } : l) }))
  const move = (i: number, d: number) => setV((s: any) => {
    const l = [...s.levels]; const [x] = l.splice(i, 1); l.splice(i + d, 0, x); return { ...s, levels: l }
  })
  const save = useMutation({ mutationFn: () => api.saveApprovalPolicy(v, policy?.name), onSuccess: (d) => { qc.setQueryData(['approval-policies'], d); onClose() } })
  const levelsOk = v.applies_to === 'Requests' || v.applies_to === 'Leave'
  const num = (k: string, label: string, hint?: string) => <Field label={t(label)} hint={hint && t(hint)}><Input type="number" min={0} value={v[k] ?? 0} onChange={(e) => set(k, e.target.value)} /></Field>
  const link = (k: string, dt: string, label: string) => <Field label={t(label)}><LinkInput doctype={dt} value={v[k] ?? ''} onChange={(x) => set(k, x)} placeholder={t('Any')} /></Field>
  return (
    <Modal open wide onClose={onClose} title={policy ? policy.policy_name : t('New approval policy')}
      footer={<><Button variant="secondary" onClick={onClose}>{t('Cancel')}</Button><Button loading={save.isPending} disabled={!v.policy_name} onClick={() => save.mutate()}>{t('Save')}</Button></>}>
      <div className="flex flex-col gap-5">
        <div className="grid gap-3 sm:grid-cols-3">
          <Field label={t('Policy name')}><Input value={v.policy_name} onChange={(e) => set('policy_name', e.target.value)} /></Field>
          <Field label={t('Applies to')}>
            <Select value={v.applies_to} onChange={(e) => set('applies_to', e.target.value)}>{meta.kinds.map((k: string) => <option key={k} value={k}>{t(k)}</option>)}</Select>
          </Field>
          <label className="flex items-center gap-2 self-end pb-2 text-sm"><input type="checkbox" className="size-4 accent-[var(--color-brand)]" checked={!!Number(v.enabled)} onChange={(e) => set('enabled', e.target.checked ? 1 : 0)} />{t('Enabled')}</label>
        </div>

        <section>
          <h3 className="mb-1 font-semibold">{t('Only when')}</h3>
          <p className="mb-3 text-sm text-muted">{t('Leave empty to apply to everyone. When several policies fit, the one with the most conditions wins.')}</p>
          <div className="grid gap-3 sm:grid-cols-3">
            {v.applies_to === 'Requests' && link('request_type', 'AlphaX Request Type', 'Request type')}
            {v.applies_to === 'Leave' && link('leave_type', 'Leave Type', 'Leave type')}
            {link('company', 'Company', 'Company')}
            {link('department', 'Department', 'Department')}
            {link('branch', 'Branch', 'Branch')}
            {link('designation', 'Designation', 'Designation')}
            {num('min_amount', 'Amount at least')}
            {num('min_days', 'Days at least')}
            {num('priority', 'Priority', 'Higher wins when two policies fit equally')}
          </div>
        </section>

        <section>
          <h3 className="mb-1 font-semibold">{t('Waiting times')}</h3>
          <p className="mb-3 text-sm text-muted">{t('Counted in working days on the employee\'s holiday list. Each approval level gets its own time.')}</p>
          <div className="grid gap-3 sm:grid-cols-3">
            {num('escalate_after_days', 'Escalate to HR after', 'Working days without a decision. 0 = never')}
            {num('remind_after_days', 'HR reminder after', 'Working days after the escalation. 0 = none')}
            <div className="flex flex-col gap-2">
              <label className="flex items-center gap-2 text-sm"><input type="checkbox" className="size-4 accent-[var(--color-brand)]" disabled={NO_AUTO.includes(v.applies_to)}
                checked={!!Number(v.auto_reject) && !NO_AUTO.includes(v.applies_to)} onChange={(e) => set('auto_reject', e.target.checked ? 1 : 0)} />{t('Reject automatically when nobody decides')}</label>
              {!!Number(v.auto_reject) && num('reject_after_days', 'Reject after', 'Working days after the reminder')}
            </div>
          </div>
          {NO_AUTO.includes(v.applies_to) && <p className="mt-2 text-xs text-muted">{t('These cannot be rejected automatically (HRMS has no rejected state for them); they are escalated and reminded only.')}</p>}
          {!!Number(v.auto_reject) && !NO_AUTO.includes(v.applies_to) && (
            <Field label={t('Comment on the automatic rejection')} hint={t('The employee sees it and can raise the request again.')}>
              <Textarea rows={2} value={v.rejection_comment ?? ''} onChange={(e) => set('rejection_comment', e.target.value)} />
            </Field>
          )}
          <div className="mt-3 rounded-xl bg-gray-50 p-3"><Timeline p={v} /></div>
        </section>

        <section>
          <div className="flex items-center justify-between gap-3">
            <h3 className="font-semibold">{t('Multi-level approval')}</h3>
            <label className="flex items-center gap-2 text-sm"><input type="checkbox" className="size-4 accent-[var(--color-brand)]" disabled={!levelsOk}
              checked={!!Number(v.multi_level) && levelsOk} onChange={(e) => set('multi_level', e.target.checked ? 1 : 0)} />{t('Use approval levels')}</label>
          </div>
          <p className="mb-3 text-sm text-muted">{levelsOk
            ? t('Most companies need only the manager. Switch levels on for the cases that need more, e.g. loans above an amount or long leave.')
            : t('Levels are available for requests and leave.')}</p>
          {!!Number(v.multi_level) && levelsOk && (
            <div className="flex flex-col gap-2">
              {v.levels.map((l: any, i: number) => (
                <div key={i} className="flex gap-3 rounded-xl border border-line p-3">
                  <span className="flex size-7 shrink-0 items-center justify-center rounded-full bg-brand-50 text-sm font-semibold text-brand">{i + 1}</span>
                  <div className="grid min-w-0 flex-1 gap-2">
                    <div className="grid gap-2 sm:grid-cols-3">
                      <Field label={t('Level name')}><Input value={l.level_label ?? ''} onChange={(e) => setLevel(i, 'level_label', e.target.value)} placeholder={t(l.approver_type)} /></Field>
                      <Field label={t('Approved by')}>
                        <Select value={l.approver_type} onChange={(e) => setLevel(i, 'approver_type', e.target.value)}>{meta.level_types.map((x: string) => <option key={x} value={x}>{t(x)}</option>)}</Select>
                      </Field>
                      {l.approver_type === 'Specific user'
                        ? <Field label={t('User')}><LinkInput doctype="User" value={l.user ?? ''} onChange={(x) => setLevel(i, 'user', x)} /></Field>
                        : <span />}
                    </div>
                    <div className="grid items-end gap-2 sm:grid-cols-[1fr_1fr_auto]">
                      <Field label={t('From amount')}><Input type="number" min={0} value={l.min_amount ?? 0} onChange={(e) => setLevel(i, 'min_amount', e.target.value)} /></Field>
                      <Field label={t('From days')}><Input type="number" min={0} value={l.min_days ?? 0} onChange={(e) => setLevel(i, 'min_days', e.target.value)} /></Field>
                      <div className="flex gap-1 pb-1">
                        <Button size="sm" variant="ghost" disabled={i === 0} onClick={() => move(i, -1)} aria-label={t('Move up')}><ArrowUp className="size-4" /></Button>
                        <Button size="sm" variant="ghost" disabled={i === v.levels.length - 1} onClick={() => move(i, 1)} aria-label={t('Move down')}><ArrowDown className="size-4" /></Button>
                        <Button size="sm" variant="ghost" onClick={() => set('levels', v.levels.filter((_: any, j: number) => j !== i))} aria-label={t('Remove')}><Trash2 className="size-4" /></Button>
                      </div>
                    </div>
                  </div>
                </div>
              ))}
              <Button size="sm" variant="secondary" className="self-start" onClick={() => set('levels', [...v.levels, { approver_type: 'Reporting manager', level_label: '' }])}>
                <Plus className="size-4" />{t('Add level')}</Button>
              <p className="text-xs text-muted">{t('A level is skipped when there is nobody to ask (e.g. no manager\'s manager) or it would be the employee themselves. "From amount / days": the level is asked only from that amount or number of days.')}</p>
              <div className="grid gap-3 sm:grid-cols-2">
                <Field label={t('When a level rejects and the employee raises it again')}>
                  <Select value={v.restart_rule} onChange={(e) => set('restart_rule', e.target.value)}>{meta.restart_rules.map((x: string) => <option key={x} value={x}>{t(x)}</option>)}</Select>
                </Field>
                <label className="flex items-center gap-2 self-end pb-2 text-sm"><input type="checkbox" className="size-4 accent-[var(--color-brand)]" checked={!!Number(v.skip_repeat)} onChange={(e) => set('skip_repeat', e.target.checked ? 1 : 0)} />{t('Skip a level when the same person already approved')}</label>
              </div>
              <p className="rounded-xl bg-brand-50 p-3 text-sm text-brand">{v.restart_rule === 'From the first level'
                ? t('Example: manager 1 and manager 2 approved, manager 3 rejected. The new request starts again with manager 1.')
                : t('Example: manager 1 and manager 2 approved, manager 3 rejected. The new request keeps those two approvals and goes straight to manager 3.')}</p>
            </div>
          )}
        </section>
        <Field label={t('Notes')}><Textarea rows={2} value={v.description ?? ''} onChange={(e) => set('description', e.target.value)} /></Field>
        {save.error && <ErrorBox error={save.error} />}
      </div>
    </Modal>
  )
}

function TryIt({ meta }: { meta: any }) {
  const { t } = useI18n()
  const [a, setA] = useState<any>({ employee: '', kind: 'Requests', request_type: '', leave_type: '', amount: 0, days: 0 })
  const q = useQuery({ queryKey: ['policy-preview', a], queryFn: () => api.previewApprovalPolicy(a), enabled: !!a.employee })
  const set = (k: string, x: any) => setA((s: any) => ({ ...s, [k]: x }))
  return (
    <Card title={t('Try it')} subtitle={t('See which policy applies to an employee and who approves, level by level.')}>
      <div className="grid gap-3 sm:grid-cols-3 lg:grid-cols-6">
        <Field label={t('Employee')}><LinkInput doctype="Employee" value={a.employee} onChange={(x) => set('employee', x)} /></Field>
        <Field label={t('Kind')}><Select value={a.kind} onChange={(e) => set('kind', e.target.value)}>{meta.kinds.filter((k: string) => k !== 'All approvals').map((k: string) => <option key={k} value={k}>{t(k)}</option>)}</Select></Field>
        {a.kind === 'Requests' && <Field label={t('Request type')}><LinkInput doctype="AlphaX Request Type" value={a.request_type} onChange={(x) => set('request_type', x)} /></Field>}
        {a.kind === 'Leave' && <Field label={t('Leave type')}><LinkInput doctype="Leave Type" value={a.leave_type} onChange={(x) => set('leave_type', x)} /></Field>}
        <Field label={t('Amount')}><Input type="number" min={0} value={a.amount} onChange={(e) => set('amount', e.target.value)} /></Field>
        <Field label={t('Days')}><Input type="number" min={0} value={a.days} onChange={(e) => set('days', e.target.value)} /></Field>
      </div>
      {q.error && <ErrorBox error={q.error} />}
      {q.data && (
        <div className="mt-3 rounded-xl bg-gray-50 p-3 text-sm">
          {!q.data.policy ? t(q.data.message) : (
            <div className="flex flex-col gap-2">
              <div><b>{q.data.policy}</b></div>
              <Timeline p={{ ...q.data, applies_to: a.kind }} />
              {q.data.levels.length > 0 && (
                <div className="flex flex-wrap items-center gap-1.5 text-xs">
                  {q.data.levels.map((l: any, i: number) => (
                    <span key={i} className="flex items-center gap-1.5">{i > 0 && <span className="text-muted">→</span>}
                      <span className="rounded-full bg-brand-50 px-2 py-0.5 text-brand">{l.label}: {l.approver_name}</span></span>
                  ))}
                </div>
              )}
            </div>
          )}
        </div>
      )}
    </Card>
  )
}

export default function ApprovalPolicies() {
  const { t } = useI18n()
  const qc = useQueryClient()
  const q = useQuery<any>({ queryKey: ['approval-policies'], queryFn: api.approvalPolicies })
  const [edit, setEdit] = useState<any | undefined>(undefined)
  const toggle = useMutation({ mutationFn: (p: any) => api.saveApprovalPolicy({ enabled: Number(p.enabled) ? 0 : 1 }, p.name),
    onSuccess: (d) => qc.setQueryData(['approval-policies'], d) })
  const del = useMutation({ mutationFn: api.deleteApprovalPolicy, onSuccess: (d) => qc.setQueryData(['approval-policies'], d) })
  if (q.isLoading) return <Spinner />
  if (q.error) return <ErrorBox error={q.error} onRetry={() => q.refetch()} />
  const d = q.data
  return (
    <div className="flex flex-col gap-5">
      <PageHeader title={t('Approval policies')}
        subtitle={t('How long approvers have, when HR is told, when a request is rejected automatically, and extra approval levels where you need them.')}
        actions={d.can_edit ? <Button onClick={() => setEdit(null)}><Plus className="size-4" />{t('New policy')}</Button> : undefined} />
      <div className="rounded-xl bg-brand-50 p-4 text-sm text-brand">
        <b>{t('How it works')}:</b> {t('the approver has the first waiting time; then HR is told; after the reminder time HR reminds the approver (you can also remind from Approval delays); if still nobody decides, the request is rejected with your comment and the employee can raise it again. Without an enabled policy, the reminder and escalation hours in Settings apply.')}
      </div>
      {d.policies.length === 0 ? <Card><Empty title={t('No approval policies yet')} /></Card> : d.policies.map((p: any) => (
        <Card key={p.name}>
          <div className="flex flex-wrap items-start gap-3">
            <div className="min-w-0 flex-1">
              <div className="flex flex-wrap items-center gap-2">
                <span className="font-semibold">{p.policy_name}</span>
                <Badge tone={Number(p.enabled) ? 'green' : 'gray'}>{Number(p.enabled) ? t('Enabled') : t('Off')}</Badge>
                <Badge tone="blue">{t(p.applies_to)}</Badge>
                {['request_type', 'leave_type', 'company', 'department', 'branch', 'designation'].filter((k) => p[k]).map((k) => <Badge key={k}>{p[k]}</Badge>)}
                {Number(p.min_amount) > 0 && <Badge>≥ {Number(p.min_amount).toLocaleString()}</Badge>}
                {Number(p.min_days) > 0 && <Badge>≥ {p.min_days} {t('days')}</Badge>}
              </div>
              {p.description && <p className="mt-1 text-sm text-muted">{p.description}</p>}
              <div className="mt-2 flex flex-col gap-2"><Timeline p={p} /><Levels p={p} /></div>
            </div>
            {d.can_edit && (
              <div className="flex items-center gap-1">
                <Button size="sm" variant="secondary" loading={toggle.isPending && toggle.variables?.name === p.name} onClick={() => toggle.mutate(p)}>
                  {Number(p.enabled) ? t('Switch off') : t('Switch on')}</Button>
                <Button size="sm" variant="ghost" onClick={() => setEdit(p)} aria-label={t('Edit')}><Pencil className="size-4" /></Button>
                <Button size="sm" variant="ghost" onClick={() => { if (window.confirm(t('Delete this policy?'))) del.mutate(p.name) }} aria-label={t('Delete')}><Trash2 className="size-4 text-red-600" /></Button>
              </div>
            )}
          </div>
        </Card>
      ))}
      {(toggle.error || del.error) && <ErrorBox error={toggle.error || del.error} />}
      <TryIt meta={d} />
      {edit !== undefined && <PolicyForm policy={edit} meta={d} onClose={() => setEdit(undefined)} />}
    </div>
  )
}
