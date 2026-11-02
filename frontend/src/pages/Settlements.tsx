import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { FileText, Plus } from 'lucide-react'
import { useState } from 'react'
import { ActivityDrawer } from '../components/ActivityDrawer'
import { LinkInput } from '../components/LinkInput'
import { Button, Card, Empty, ErrorBox, Field, Input, Modal, PageHeader, Select, Spinner, StatusBadge, Table, Textarea } from '../components/ui'
import { api, downloadUrl } from '../lib/api'
import { fmtDate, fmtMoney, fmtNumber, todayISO } from '../lib/format'
import { useI18n } from '../lib/i18n'
import { useSession } from '../lib/session'

const REASONS = ['Termination by employer', 'End of fixed-term contract', 'Resignation', 'Resignation – Article 87 exception', 'Dismissal under Article 80']

function SettlementForm({ initial, onClose }: { initial: any; onClose: () => void }) {
  const { t, lang } = useI18n()
  const qc = useQueryClient()
  const [f, setF] = useState<any>(initial ?? { exit_date: todayISO(), reason: REASONS[2], mode: 'With payroll' })
  const set = (k: string, v: any) => setF((s: any) => ({ ...s, [k]: v }))
  const m = useMutation({ mutationFn: () => api.prepareSettlement({ ...f, name: f.name || undefined }),
    onSuccess: (d) => { setF(d); qc.invalidateQueries({ queryKey: ['settlements'] }) } })
  const num = (k: string, label: string, hint?: string) => (
    <Field label={label} hint={hint}><Input type="number" step="0.01" value={f[k] ?? ''} onChange={(e) => set(k, e.target.value === '' ? null : e.target.value)} /></Field>
  )
  const r = m.data ?? (f.net_amount !== undefined ? f : null)
  return (
    <Modal open onClose={onClose} wide title={f.name ? `${t('Final settlement')} · ${f.employee_name ?? f.name}` : t('New final settlement')}
      footer={<><Button variant="secondary" onClick={onClose}>{t('Close')}</Button>
        <Button disabled={!f.employee || f.status && f.status !== 'Draft'} loading={m.isPending} onClick={() => m.mutate()}>{t('Calculate & save draft')}</Button></>}>
      <div className="grid gap-4 md:grid-cols-2">
        <div className="grid gap-3">
          <Field label={t('Employee')}><LinkInput doctype="Employee" value={f.employee ?? ''} onChange={(v) => set('employee', v)} disabled={!!f.name} /></Field>
          <Field label={t('Last working day')}><Input type="date" value={f.exit_date ?? ''} onChange={(e) => set('exit_date', e.target.value)} /></Field>
          <Field label={t('Reason')}><Select value={f.reason} onChange={(e) => set('reason', e.target.value)}>{REASONS.map((x) => <option key={x} value={x}>{t(x)}</option>)}</Select></Field>
          <Field label={t('Payment')}><Select value={f.mode} onChange={(e) => set('mode', e.target.value)}>
            <option value="With payroll">{t('With payroll')}</option><option value="Separate payment">{t('Separate payment')}</option></Select></Field>
          {num('monthly_wage', t('Monthly wage (optional)'), t('Empty = last salary slip'))}
          {num('leave_days', t('Unused annual leave (days)'), t('Empty = balance on the last day'))}
          {f.mode === 'Separate payment' && num('unpaid_days', t('Unpaid salary days'))}
          {num('other_earnings', t('Other earnings'))}
          {num('advances', t('Advances / loans to recover'), t('Empty = outstanding advances'))}
          {num('other_deductions', t('Other deductions'))}
          <Field label={t('Notes')}><Textarea value={f.notes ?? ''} onChange={(e) => set('notes', e.target.value)} /></Field>
        </div>
        <div>
          {m.error && <ErrorBox error={m.error} />}
          {r && r.net_amount !== undefined && r.net_amount !== null ? (
            <table className="w-full text-sm">
              <tbody className="divide-y divide-line">
                <tr><td className="py-1.5">{t('Service')}</td><td className="text-end">{fmtNumber(r.service_years, lang, 2)} {t('years')}</td></tr>
                <tr><td className="py-1.5">{t('Monthly wage')}</td><td className="text-end">{fmtMoney(r.monthly_wage, lang)}</td></tr>
                <tr><td className="py-1.5">{t('End-of-service award')} ×{r.eosb_factor}</td><td className="text-end">{fmtMoney(r.eosb_amount, lang)}</td></tr>
                <tr><td className="py-1.5">{t('Leave encashment')} ({r.leave_days})</td><td className="text-end">{fmtMoney(r.leave_amount, lang)}</td></tr>
                {r.unpaid_salary > 0 && <tr><td className="py-1.5">{t('Unpaid salary')}</td><td className="text-end">{fmtMoney(r.unpaid_salary, lang)}</td></tr>}
                {r.other_earnings > 0 && <tr><td className="py-1.5">{t('Other earnings')}</td><td className="text-end">{fmtMoney(r.other_earnings, lang)}</td></tr>}
                {r.advances > 0 && <tr><td className="py-1.5">{t('Advances / loans to recover')}</td><td className="text-end">-{fmtMoney(r.advances, lang)}</td></tr>}
                {r.other_deductions > 0 && <tr><td className="py-1.5">{t('Other deductions')}</td><td className="text-end">-{fmtMoney(r.other_deductions, lang)}</td></tr>}
                <tr className="font-semibold"><td className="py-2">{t('Net settlement')}</td><td className="text-end">{fmtMoney(r.net_amount, lang)}</td></tr>
              </tbody>
            </table>
          ) : <p className="text-sm text-muted">{t('Fill in the details and calculate.')}</p>}
        </div>
      </div>
    </Modal>
  )
}

export default function Settlements() {
  const { t, lang } = useI18n()
  const s = useSession()
  const qc = useQueryClient()
  const [status, setStatus] = useState('')
  const [edit, setEdit] = useState<any>(undefined)
  const [trail, setTrail] = useState<string | null>(null)
  const [cancel, setCancel] = useState<any>(null)
  const [reason, setReason] = useState('')
  const q = useQuery({ queryKey: ['settlements', status], queryFn: () => api.settlements(status || undefined) })
  const inv = () => qc.invalidateQueries({ queryKey: ['settlements'] })
  const approve = useMutation({ mutationFn: api.approveSettlement, onSuccess: inv })
  const pay = useMutation({ mutationFn: (n: string) => api.paySettlement(n), onSuccess: inv })
  const cm = useMutation({ mutationFn: () => api.cancelSettlement(cancel.name, reason), onSuccess: () => { setCancel(null); setReason(''); inv() } })
  const manager = s.persona.hr_manager
  return (
    <div>
      <PageHeader title={t('Final settlements')} subtitle={t('End-of-service award, leave encashment and final dues — with payroll or separately')}
        actions={<div className="flex gap-2">
          <Select className="w-40" value={status} onChange={(e) => setStatus(e.target.value)}>
            <option value="">{t('All')}</option>{['Draft', 'Approved', 'Paid', 'Cancelled'].map((x) => <option key={x} value={x}>{t(x)}</option>)}
          </Select>
          <Button onClick={() => setEdit(null)}><Plus className="size-4" />{t('New final settlement')}</Button>
        </div>} />
      <Card>
        {q.isLoading ? <Spinner /> : q.error ? <ErrorBox error={q.error} /> : !q.data?.length ? <Empty title={t('No final settlements')} icon={<FileText />} /> : (
          <Table head={[t('Employee'), t('Last working day'), t('Reason'), t('Payment'), t('Net settlement'), t('Status'), '']}>
            {q.data.map((r: any) => (
              <tr key={r.name}>
                <td className="py-2"><button className="font-medium hover:underline" onClick={() => setTrail(r.name)}>{r.employee_name}</button><div className="text-xs text-muted">{r.name}</div></td>
                <td>{fmtDate(r.exit_date, lang)}</td><td className="text-sm">{t(r.reason)}</td><td className="text-sm">{t(r.mode)}</td>
                <td className="tabular-nums">{fmtMoney(r.net_amount, lang)}</td><td><StatusBadge status={r.status} /></td>
                <td className="whitespace-nowrap">
                  <a className="me-2 text-sm text-brand underline" href={downloadUrl('settlements.statement', { name: r.name })} target="_blank" rel="noreferrer">PDF</a>
                  {r.status === 'Draft' && <Button size="sm" variant="secondary" onClick={() => setEdit(r)}>{t('Edit')}</Button>}
                  {r.status === 'Draft' && manager && <Button size="sm" loading={approve.isPending && approve.variables === r.name} onClick={() => approve.mutate(r.name)}>{t('Approve')}</Button>}
                  {r.status === 'Approved' && manager && <Button size="sm" loading={pay.isPending} onClick={() => pay.mutate(r.name)}>{t('Mark paid')}</Button>}
                  {['Draft', 'Approved'].includes(r.status) && manager && <Button size="sm" variant="secondary" onClick={() => setCancel(r)}>{t('Cancel')}</Button>}
                </td>
              </tr>
            ))}
          </Table>
        )}
        {(approve.error || pay.error) && <ErrorBox error={approve.error || pay.error} />}
      </Card>
      {edit !== undefined && <SettlementForm initial={edit} onClose={() => setEdit(undefined)} />}
      {trail && <ActivityDrawer doctype="AlphaX Final Settlement" name={trail} onClose={() => setTrail(null)} />}
      <Modal open={!!cancel} onClose={() => setCancel(null)} title={t('Cancel')}
        footer={<><Button variant="secondary" onClick={() => setCancel(null)}>{t('Close')}</Button>
          <Button variant="danger" disabled={!reason.trim()} loading={cm.isPending} onClick={() => cm.mutate()}>{t('Cancel')}</Button></>}>
        <p className="mb-2 text-sm text-muted">{t('Any payroll additions are reversed.')}</p>
        <Textarea placeholder={t('Reason')} value={reason} onChange={(e) => setReason(e.target.value)} />
        {cm.error && <ErrorBox error={cm.error} />}
      </Modal>
    </div>
  )
}
