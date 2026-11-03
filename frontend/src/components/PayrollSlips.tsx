import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Eye, RefreshCw, Search, SlidersHorizontal, Trash2, Undo2, UserPlus } from 'lucide-react'
import { useState } from 'react'
import { api } from '../lib/api'
import { fmtMoney, fmtNumber } from '../lib/format'
import { useI18n } from '../lib/i18n'
import { Button, Card, ErrorBox, Field, Input, Modal, Select, Spinner, StatusBadge, Textarea } from './ui'

/** Every slip of the month, with per-employee corrections — no need to cancel and re-run the whole payroll. */
export function PayrollSlips({ company, month, closed, canManage, run }: { company: string; month: string; closed: boolean; canManage: boolean; run?: string }) {
  const { t, lang } = useI18n()
  const qc = useQueryClient()
  const q = useQuery({ queryKey: ['payroll-slips', company, month, run], queryFn: () => api.payrollSlips(company, month, run) })
  const comps = useQuery({ queryKey: ['salary-components'], queryFn: api.salaryComponents, staleTime: 300_000 })
  const [search, setSearch] = useState('')
  const [view, setView] = useState<string | null>(null)
  const [adjust, setAdjust] = useState<any>(null)
  const [reasonFor, setReasonFor] = useState<{ row: any; kind: 'remove' | 'redo' } | null>(null)
  const [reason, setReason] = useState('')
  const refresh = () => { qc.invalidateQueries({ queryKey: ['payroll-slips'] }); qc.invalidateQueries({ queryKey: ['payroll-period'] }) }
  const preview = useQuery({ queryKey: ['payslip-preview', view], queryFn: () => api.payslipPreview(view!), enabled: !!view })
  const recalc = useMutation({ mutationFn: api.recalcSlip, onSuccess: refresh })
  const add = useMutation({ mutationFn: (e: string) => api.addSlipEmployee(company, month, e, run), onSuccess: refresh })
  const act = useMutation({
    mutationFn: () => reasonFor!.kind === 'remove' ? api.removeSlip(reasonFor!.row.name, reason) : api.redoSlip(reasonFor!.row.name, reason),
    onSuccess: () => { setReasonFor(null); setReason(''); refresh() },
  })
  const adj = useMutation({ mutationFn: () => api.adjustPay({ company, month, ...adjust }), onSuccess: () => { setAdjust(null); refresh() } })
  const rows = (q.data?.rows ?? []).filter((r: any) => !search || `${r.employee_name} ${r.employee} ${r.department ?? ''}`.toLowerCase().includes(search.toLowerCase()))
  const money = (v: number) => fmtMoney(v, lang)
  return (
    <Card title={t('Salary slips')} subtitle={t('Fix one employee without re-running the whole payroll')}
      action={<div className="relative w-56"><Search className="pointer-events-none absolute start-2.5 top-1/2 size-4 -translate-y-1/2 text-muted" />
        <Input className="ps-8" placeholder={t('Search employee')} value={search} onChange={(e) => setSearch(e.target.value)} /></div>}>
      {q.isLoading ? <Spinner /> : q.error ? <ErrorBox error={q.error} /> : (
        <>
          {!!q.data.missing.length && !closed && (
            <div className="mb-3 rounded-xl bg-amber-50 p-3 text-sm text-amber-900">
              <div className="mb-1 font-medium">{t('Have a salary structure but no slip this month')}</div>
              <div className="flex flex-wrap gap-2">{q.data.missing.map((m: any) => (
                <Button key={m.employee} size="sm" variant="secondary" loading={add.isPending && add.variables === m.employee} onClick={() => add.mutate(m.employee)}>
                  <UserPlus className="size-4" />{m.employee_name}</Button>))}</div>
            </div>
          )}
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead><tr className="text-start text-xs text-muted">
                {[t('Employee'), t('Paid days'), t('Gross pay'), 'GOSI', t('Loans'), t('Deductions'), t('Net pay'), t('Status'), ''].map((h, i) =>
                  <th key={i} className={`px-2 pb-2 font-medium ${i > 0 && i < 7 ? 'text-end' : 'text-start'}`}>{h}</th>)}
              </tr></thead>
              <tbody className="divide-y divide-line">
                {rows.map((r: any) => (
                  <tr key={r.name}>
                    <td className="px-2 py-2"><div className="font-medium">{r.employee_name}</div><div className="text-xs text-muted">{r.employee}</div></td>
                    <td className="px-2 text-end tabular-nums">{fmtNumber(r.payment_days, lang, 1)}/{fmtNumber(r.total_working_days, lang, 0)}</td>
                    <td className="px-2 text-end tabular-nums">{money(r.gross_pay)}</td>
                    <td className="px-2 text-end tabular-nums">{r.gosi ? money(r.gosi) : '—'}</td>
                    <td className="px-2 text-end tabular-nums">{r.total_loan_repayment ? money(r.total_loan_repayment) : '—'}</td>
                    <td className="px-2 text-end tabular-nums">{money(r.total_deduction)}</td>
                    <td className="px-2 text-end font-semibold tabular-nums">{money(r.net_pay)}</td>
                    <td className="px-2"><StatusBadge status={r.docstatus === 0 ? 'Draft' : 'Submitted'} /></td>
                    <td className="whitespace-nowrap px-2 text-end">
                      <button className="rounded p-1.5 hover:bg-surface" title={t('View payslip')} onClick={() => setView(r.name)}><Eye className="size-4" /></button>
                      {!closed && <button className="rounded p-1.5 hover:bg-surface" title={t('Add an earning or deduction')} onClick={() => setAdjust({ employee: r.employee, name: r.employee_name, when: r.docstatus === 0 ? 'this' : 'next', amount: '', salary_component: '' })}><SlidersHorizontal className="size-4" /></button>}
                      {!closed && r.docstatus === 0 && <button className="rounded p-1.5 hover:bg-surface" title={t('Recalculate (after fixing attendance, leave or salary)')} onClick={() => recalc.mutate(r.name)}>
                        <RefreshCw className={`size-4 ${recalc.isPending && recalc.variables === r.name ? 'animate-spin' : ''}`} /></button>}
                      {!closed && canManage && r.docstatus === 0 && <button className="rounded p-1.5 text-red-700 hover:bg-red-50" title={t('Remove from this run')} onClick={() => setReasonFor({ row: r, kind: 'remove' })}><Trash2 className="size-4" /></button>}
                      {!closed && canManage && r.can_redo && <button className="rounded p-1.5 hover:bg-surface" title={t('Cancel and redo this slip')} onClick={() => setReasonFor({ row: r, kind: 'redo' })}><Undo2 className="size-4" /></button>}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          {(recalc.error || add.error) && <ErrorBox error={recalc.error || add.error} />}
        </>
      )}
      {view && <Modal open wide onClose={() => setView(null)} title={t('Payslip preview')}>
        {preview.isLoading ? <Spinner /> : preview.error ? <ErrorBox error={preview.error} /> : <div className="overflow-x-auto" dangerouslySetInnerHTML={{ __html: preview.data?.html ?? '' }} />}
      </Modal>}
      {adjust && <Modal open onClose={() => setAdjust(null)} title={`${t('Add an earning or deduction')} · ${adjust.name}`}
        footer={<><Button variant="secondary" onClick={() => setAdjust(null)}>{t('Cancel')}</Button>
          <Button disabled={!adjust.salary_component || !(Number(adjust.amount) > 0)} loading={adj.isPending} onClick={() => adj.mutate()}>{t('Save')}</Button></>}>
        <div className="grid gap-3">
          <Field label={t('Component')}><Select value={adjust.salary_component} onChange={(e) => setAdjust({ ...adjust, salary_component: e.target.value })}>
            <option value="">—</option>
            {(comps.data ?? []).map((c: any) => <option key={c.name} value={c.name}>{c.name} ({t(c.type)})</option>)}</Select></Field>
          <Field label={t('Amount')}><Input type="number" min="0" step="0.01" value={adjust.amount} onChange={(e) => setAdjust({ ...adjust, amount: e.target.value })} /></Field>
          <Field label={t('Apply in')}><Select value={adjust.when} onChange={(e) => setAdjust({ ...adjust, when: e.target.value })}>
            <option value="this">{t('This month (slip is recalculated)')}</option><option value="next">{t('Next month')}</option></Select></Field>
          <Field label={t('Note')}><Textarea value={adjust.note ?? ''} onChange={(e) => setAdjust({ ...adjust, note: e.target.value })} /></Field>
          {adj.error && <ErrorBox error={adj.error} />}
        </div>
      </Modal>}
      {reasonFor && <Modal open onClose={() => setReasonFor(null)} title={reasonFor.kind === 'remove' ? t('Remove from this run') : t('Cancel and redo this slip')}
        footer={<><Button variant="secondary" onClick={() => setReasonFor(null)}>{t('Close')}</Button>
          <Button variant={reasonFor.kind === 'remove' ? 'danger' : 'primary'} disabled={!reason.trim()} loading={act.isPending} onClick={() => act.mutate()}>{reasonFor.kind === 'remove' ? t('Remove') : t('Redo')}</Button></>}>
        <p className="mb-2 text-sm text-muted">{reasonFor.kind === 'remove' ? t('The employee can be added back to this run later (e.g. salary on hold).') : t('The submitted slip is cancelled and a corrected draft is made. Submit it again when it is right.')}</p>
        <Textarea placeholder={t('Reason')} value={reason} onChange={(e) => setReason(e.target.value)} />
        {act.error && <div className="mt-2"><ErrorBox error={act.error} /></div>}
      </Modal>}
    </Card>
  )
}
