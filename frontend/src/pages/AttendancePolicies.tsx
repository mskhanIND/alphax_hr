import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Plus, ShieldCheck } from 'lucide-react'
import { useState } from 'react'
import { LinkInput } from '../components/LinkInput'
import { Badge, Button, Card, Empty, ErrorBox, Field, Input, Modal, PageHeader, Select, Spinner, Table, Textarea } from '../components/ui'
import { api } from '../lib/api'
import { useI18n } from '../lib/i18n'

const TARGETS = ['Everyone', 'Company', 'Department', 'Designation', 'Employee'] as const

function rulesText(p: any, t: (s: string) => string) {
  const out: string[] = []
  if (p.exempt) out.push(t('Exempt from attendance'))
  if (p.late_grace_minutes !== null && p.late_grace_minutes !== '') out.push(`${t('Late grace')} ${p.late_grace_minutes} ${t('min')}`)
  if (p.early_grace_minutes !== null && p.early_grace_minutes !== '') out.push(`${t('Early-exit grace')} ${p.early_grace_minutes} ${t('min')}`)
  if (p.monthly_late_allowance) out.push(`${p.monthly_late_allowance} ${t('free late minutes / month')}`)
  if (p.single_punch_ok) out.push(t('Single punch OK'))
  if (p.permissions_per_month !== null && p.permissions_per_month !== '') out.push(`${p.permissions_per_month} ${t('permissions / month')}`)
  if (p.no_penalties) out.push(t('No penalties'))
  return out
}

function PolicyForm({ initial, onClose }: { initial: any; onClose: () => void }) {
  const { t } = useI18n()
  const qc = useQueryClient()
  const [f, setF] = useState<any>(initial ?? { applies_to: 'Department', enabled: 1 })
  const set = (k: string, v: any) => setF((s: any) => ({ ...s, [k]: v }))
  const m = useMutation({ mutationFn: () => api.saveAttendancePolicy(f, initial?.name),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ['attendance-policies'] }); onClose() } })
  const target = f.applies_to?.toLowerCase()
  const check = (k: string, label: string, hint?: string) => (
    <label className="flex items-start gap-2 text-sm"><input type="checkbox" className="mt-0.5 size-4" checked={!!f[k]} onChange={(e) => set(k, e.target.checked ? 1 : 0)} />
      <span>{label}{hint && <span className="block text-xs text-muted">{hint}</span>}</span></label>
  )
  return (
    <Modal open onClose={onClose} wide title={initial ? initial.policy_name : t('New attendance policy')}
      footer={<><Button variant="secondary" onClick={onClose}>{t('Cancel')}</Button><Button loading={m.isPending} disabled={!f.policy_name} onClick={() => m.mutate()}>{t('Save')}</Button></>}>
      <div className="grid gap-4 md:grid-cols-2">
        <div className="grid content-start gap-3">
          <Field label={t('Policy name')}><Input value={f.policy_name ?? ''} disabled={!!initial} onChange={(e) => set('policy_name', e.target.value)} /></Field>
          <Field label={t('Applies to')}>
            <Select value={f.applies_to} onChange={(e) => set('applies_to', e.target.value)}>{TARGETS.map((x) => <option key={x} value={x}>{t(x)}</option>)}</Select>
          </Field>
          {target !== 'everyone' && (
            <Field label={t(f.applies_to)}><LinkInput doctype={f.applies_to} value={f[target] ?? ''} onChange={(v) => set(target, v)} /></Field>
          )}
          <Field label={t('Notes')}><Textarea value={f.description ?? ''} onChange={(e) => set('description', e.target.value)} /></Field>
          {check('enabled', t('Enabled'))}
        </div>
        <div className="grid content-start gap-3">
          {check('exempt', t('Exempt from attendance tracking'), t('No late, early, absent or missing-punch flags (executives, field staff, drivers).'))}
          <div className="grid grid-cols-2 gap-3">
            <Field label={t('Late grace (min)')} hint={t('Blank = shift')}><Input inputMode="numeric" value={f.late_grace_minutes ?? ''} onChange={(e) => set('late_grace_minutes', e.target.value)} /></Field>
            <Field label={t('Early-exit grace (min)')} hint={t('Blank = shift')}><Input inputMode="numeric" value={f.early_grace_minutes ?? ''} onChange={(e) => set('early_grace_minutes', e.target.value)} /></Field>
            <Field label={t('Free late minutes / month')}><Input type="number" min="0" value={f.monthly_late_allowance ?? ''} onChange={(e) => set('monthly_late_allowance', e.target.value === '' ? 0 : Number(e.target.value))} /></Field>
            <Field label={t('Permissions / month')} hint={t('Blank = company setting, 0 = no limit')}><Input inputMode="numeric" value={f.permissions_per_month ?? ''} onChange={(e) => set('permissions_per_month', e.target.value)} /></Field>
          </div>
          {check('single_punch_ok', t('A single punch counts as present'), t('Missing check-out is not flagged.'))}
          {check('no_penalties', t('Never suggest penalties'))}
        </div>
      </div>
      {m.error && <div className="mt-3"><ErrorBox error={m.error} /></div>}
    </Modal>
  )
}

export default function AttendancePolicies() {
  const { t } = useI18n()
  const qc = useQueryClient()
  const q = useQuery({ queryKey: ['attendance-policies'], queryFn: api.attendancePolicies })
  const [edit, setEdit] = useState<any>(undefined)
  const del = useMutation({ mutationFn: api.deleteAttendancePolicy, onSuccess: () => qc.invalidateQueries({ queryKey: ['attendance-policies'] }) })
  return (
    <div>
      <PageHeader title={t('Attendance exceptions')} subtitle={t('Who is exempt, grace periods, free late minutes and permission limits. The most specific policy wins.')}
        actions={<Button onClick={() => setEdit(null)}><Plus className="size-4" />{t('New policy')}</Button>} />
      <Card>
        {q.isLoading ? <Spinner /> : q.error ? <ErrorBox error={q.error} /> : !q.data?.length
          ? <Empty title={t('No exceptions yet')} icon={<ShieldCheck />}>{t('Everyone follows their shift rules.')}</Empty> : (
          <Table head={[t('Policy'), t('Applies to'), t('Employees'), t('Rules'), '']}>
            {q.data.map((p: any) => (
              <tr key={p.name}>
                <td className="py-2 font-medium">{p.policy_name}{!p.enabled && <> <Badge>{t('Disabled')}</Badge></>}</td>
                <td className="text-sm">{t(p.applies_to)}{p.applies_to !== 'Everyone' ? `: ${p[p.applies_to.toLowerCase()] ?? ''}` : ''}</td>
                <td>{p.covers}</td>
                <td><div className="flex flex-wrap gap-1">{rulesText(p, t).map((r) => <Badge key={r} tone="blue">{r}</Badge>)}</div></td>
                <td className="whitespace-nowrap"><Button size="sm" variant="secondary" onClick={() => setEdit(p)}>{t('Edit')}</Button>
                  <Button size="sm" variant="secondary" loading={del.isPending && del.variables === p.name} onClick={() => del.mutate(p.name)}>{t('Delete')}</Button></td>
              </tr>
            ))}
          </Table>
        )}
        {del.error && <ErrorBox error={del.error} />}
      </Card>
      {edit !== undefined && <PolicyForm initial={edit} onClose={() => setEdit(undefined)} />}
    </div>
  )
}
