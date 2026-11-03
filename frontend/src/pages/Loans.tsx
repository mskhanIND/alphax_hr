import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { AlertTriangle, Banknote, CalendarClock, HandCoins, Plus } from 'lucide-react'
import { useEffect, useState } from 'react'
import { LinkInput } from '../components/LinkInput'
import { Badge, Button, Card, Empty, ErrorBox, Field, Input, Modal, PageHeader, Select, Spinner, Stat, StatusBadge, Table, Textarea } from '../components/ui'
import { api } from '../lib/api'
import { fmtDate, fmtMoney, fmtMonth, monthStart, shiftMonth, todayISO } from '../lib/format'
import { useI18n } from '../lib/i18n'

const ROW_TONE: Record<string, string> = { Scheduled: 'gray', 'In payroll': 'blue', Deducted: 'green', Postponed: 'amber', Settled: 'green', Cancelled: 'gray' }

export function LoanSchedule({ loan, onPostpone }: { loan: any; onPostpone?: (row: any) => void }) {
  const { t, lang } = useI18n()
  return (
    <Table head={[t('Month'), t('Amount'), t('Status'), t('Note'), '']}>
      {loan.schedule.map((r: any) => (
        <tr key={r.name}>
          <td className="py-1.5">{fmtMonth(r.due_month, lang)}</td>
          <td>{fmtMoney(r.amount, lang)}</td>
          <td><Badge tone={ROW_TONE[r.status]}>{t(r.status)}</Badge></td>
          <td className="text-xs text-muted">{r.note}</td>
          <td>{onPostpone && ['Scheduled', 'In payroll'].includes(r.status) && <Button size="sm" variant="ghost" onClick={() => onPostpone(r)}>{t('Postpone')}</Button>}</td>
        </tr>
      ))}
    </Table>
  )
}

function NewLoan({ onClose, onDone }: { onClose: () => void; onDone: (name: string) => void }) {
  const { t, lang } = useI18n()
  const [d, setD] = useState<any>({ employee: '', loan_type: 'Loan', amount: '', installments: 6, first_month: shiftMonth(monthStart(todayISO()), 1), purpose: '', consent: 0 })
  const set = (k: string, v: unknown) => setD({ ...d, [k]: v })
  const ready = d.employee && Number(d.amount) > 0
  const pv = useQuery({ queryKey: ['loan-preview', d], queryFn: () => api.previewLoan({ ...d, installments: d.loan_type === 'Salary advance' ? d.installments || 1 : d.installments }),
    enabled: !!ready, retry: false })
  const m = useMutation({ mutationFn: () => api.createLoan(d), onSuccess: (r: any) => onDone(r.name) })
  return (
    <Modal open wide onClose={onClose} title={t('New loan or salary advance')}
      footer={<><Button variant="secondary" onClick={onClose}>{t('Cancel')}</Button>
        <Button disabled={!ready || !!pv.data?.problems?.length} loading={m.isPending} onClick={() => m.mutate()}>{t('Approve')}</Button></>}>
      <div className="grid gap-3 sm:grid-cols-2">
        <Field label={t('Employee')}><LinkInput doctype="Employee" value={d.employee} onChange={(v) => set('employee', v)} /></Field>
        <Field label={t('Type')}><Select value={d.loan_type} onChange={(e) => setD({ ...d, loan_type: e.target.value, installments: e.target.value === 'Salary advance' ? 1 : 6 })}>
          <option value="Loan">{t('Loan')}</option><option value="Salary advance">{t('Salary advance')}</option></Select></Field>
        <Field label={t('Amount')}><Input type="number" min={0} value={d.amount} onChange={(e) => set('amount', e.target.value)} /></Field>
        <Field label={t('Installments (months)')}><Input type="number" min={1} value={d.installments} onChange={(e) => set('installments', Number(e.target.value) || 1)} /></Field>
        <Field label={t('First deduction month')}><Input type="month" value={d.first_month.slice(0, 7)} onChange={(e) => set('first_month', `${e.target.value}-01`)} /></Field>
        <Field label={t('Purpose')}><Input value={d.purpose} onChange={(e) => set('purpose', e.target.value)} /></Field>
      </div>
      <label className="mt-3 flex items-start gap-2 text-sm">
        <input type="checkbox" className="mt-0.5 size-4 accent-[var(--color-brand)]" checked={!!d.consent} onChange={(e) => set('consent', e.target.checked ? 1 : 0)} />
        {t('The employee gave written consent to installments above 10% of the wage (Art. 92). Attach it to the loan after saving.')}
      </label>
      {pv.isFetching && <Spinner />}
      {pv.error && <ErrorBox error={pv.error} />}
      {pv.data && (
        <div className="mt-4 flex flex-col gap-3">
          <div className="grid grid-cols-2 gap-2 text-sm sm:grid-cols-4">
            <div className="rounded-xl bg-surface p-2"><div className="text-xs text-muted">{t('Monthly wage')}</div>{fmtMoney(pv.data.wage, lang)}</div>
            <div className="rounded-xl bg-surface p-2"><div className="text-xs text-muted">{t('10% of wage')}</div>{fmtMoney(pv.data.loan_cap, lang)}</div>
            <div className="rounded-xl bg-surface p-2"><div className="text-xs text-muted">{t('Half the wage')}</div>{fmtMoney(pv.data.half_wage, lang)}</div>
            {d.loan_type === 'Loan' && <div className="rounded-xl bg-surface p-2"><div className="text-xs text-muted">{t('Fewest months without consent')}</div>{pv.data.min_months}</div>}
          </div>
          {pv.data.problems.length > 0 && (
            <div className="rounded-xl bg-red-50 p-3 text-sm text-red-800"><div className="mb-1 flex items-center gap-1.5 font-medium"><AlertTriangle className="size-4" />{t('Saudi Labor Law limits')}</div>
              <ul className="list-disc ps-5">{pv.data.problems.map((p: string, i: number) => <li key={i}>{p}</li>)}</ul></div>
          )}
          <div className="flex flex-wrap gap-1.5 text-xs">
            {pv.data.schedule.map((r: any) => <span key={r.due_month} className="rounded-lg bg-surface px-2 py-1">{fmtMonth(r.due_month, lang)}: {fmtMoney(r.amount, lang)}</span>)}
          </div>
        </div>
      )}
      {m.error && <div className="mt-3"><ErrorBox error={m.error} /></div>}
    </Modal>
  )
}

function LoanDetail({ name, accounts, onClose }: { name: string; accounts: any[]; onClose: () => void }) {
  const { t, lang } = useI18n()
  const qc = useQueryClient()
  const q = useQuery({ queryKey: ['loan', name], queryFn: () => api.loan(name) })
  const [act, setAct] = useState<null | 'pay' | 'postpone' | 'settle' | 'cancel'>(null)
  const [row, setRow] = useState<any>(null)
  const [mode, setMode] = useState('Bank transfer')
  const [account, setAccount] = useState('')
  const [months, setMonths] = useState(1)
  const [month, setMonth] = useState(monthStart(todayISO()))
  const [note, setNote] = useState('')
  const l = q.data
  useEffect(() => { setAccount('') }, [mode])
  const done = (d: any) => { qc.setQueryData(['loan', name], d); qc.invalidateQueries({ queryKey: ['loans'] }); setAct(null); setNote('') }
  const m = useMutation({
    mutationFn: () => act === 'pay' ? api.disburseLoan(name, mode, account || undefined)
      : act === 'postpone' ? api.postponeLoan(name, row?.name, months, note)
      : act === 'settle' ? api.settleLoan(name, mode, account || undefined, month, 1)
      : api.cancelLoan(name, note),
    onSuccess: done,
  })
  const acc = accounts.filter((a: any) => a.company === l?.company && a.account_type === (mode === 'Cash' ? 'Cash' : 'Bank'))
  return (
    <Modal open wide onClose={onClose} title={l ? `${t(l.loan_type)} · ${l.employee_name}` : t('Loan')}>
      {q.isLoading ? <Spinner /> : q.error ? <ErrorBox error={q.error} /> : l && (
        <div className="flex flex-col gap-4">
          <div className="grid grid-cols-2 gap-2 text-sm sm:grid-cols-4">
            <div className="rounded-xl bg-surface p-2"><div className="text-xs text-muted">{t('Amount')}</div><b>{fmtMoney(l.amount, lang)}</b></div>
            <div className="rounded-xl bg-surface p-2"><div className="text-xs text-muted">{t('Repaid')}</div>{fmtMoney(l.repaid, lang)}</div>
            <div className="rounded-xl bg-surface p-2"><div className="text-xs text-muted">{t('Outstanding')}</div><b>{fmtMoney(l.outstanding, lang)}</b></div>
            <div className="rounded-xl bg-surface p-2"><div className="text-xs text-muted">{t('Status')}</div><StatusBadge status={l.status} /></div>
          </div>
          <p className="text-xs text-muted">
            {l.name}{l.purpose ? ` · ${l.purpose}` : ''}{l.paid_by ? ` · ${t('Paid by')} ${t(l.paid_by)} ${fmtDate(l.disbursed_on, lang)}` : ''}
            {l.consent ? ` · ${t('Written consent above 10%')}` : ''}{l.request ? ` · ${t('From request')} ${l.request}` : ''}
          </p>
          <div className="flex flex-wrap gap-2">
            {l.status === 'Approved' && <Button onClick={() => setAct('pay')}><Banknote className="size-4" />{t('Pay out')}</Button>}
            {['Approved', 'Disbursed', 'Repaying'].includes(l.status) && <Button variant="secondary" onClick={() => { setRow(null); setAct('postpone') }}><CalendarClock className="size-4" />{t('Postpone next installment')}</Button>}
            {['Disbursed', 'Repaying'].includes(l.status) && <Button variant="secondary" onClick={() => setAct('settle')}><HandCoins className="size-4" />{t('Settle at once')}</Button>}
            {l.status === 'Approved' && <Button variant="ghost" onClick={() => setAct('cancel')}>{t('Cancel')}</Button>}
          </div>
          <LoanSchedule loan={l} onPostpone={['Approved', 'Disbursed', 'Repaying'].includes(l.status) ? (r) => { setRow(r); setAct('postpone') } : undefined} />
          {act && (
            <div className="rounded-xl border border-line p-3">
              <div className="mb-2 text-sm font-semibold">{t(act === 'pay' ? 'Pay out' : act === 'postpone' ? 'Postpone installment' : act === 'settle' ? 'One-time settlement' : 'Cancel')}</div>
              {(act === 'pay' || act === 'settle') && (
                <div className="grid gap-3 sm:grid-cols-3">
                  <Field label={act === 'pay' ? t('Paid by') : t('Settled by')}>
                    <Select value={mode} onChange={(e) => setMode(e.target.value)}>
                      {act === 'settle' && <option value="payroll">{t('Deduct from one salary')}</option>}
                      <option value="Bank transfer">{t('Bank transfer')}</option><option value="Cash">{t('Cash')}</option>
                    </Select>
                  </Field>
                  {mode !== 'payroll' ? (
                    <Field label={t('Account')} hint={t('Blank: the company default')}>
                      <Select value={account} onChange={(e) => setAccount(e.target.value)}><option value="">—</option>{acc.map((a: any) => <option key={a.name}>{a.name}</option>)}</Select>
                    </Field>
                  ) : (
                    <Field label={t('Payroll month')}><Input type="month" value={month.slice(0, 7)} onChange={(e) => setMonth(`${e.target.value}-01`)} /></Field>
                  )}
                </div>
              )}
              {act === 'postpone' && (
                <Field label={t('Postpone by (months)')}><Input type="number" min={1} className="!w-24" value={months} onChange={(e) => setMonths(Number(e.target.value) || 1)} /></Field>
              )}
              {(act === 'postpone' || act === 'cancel') && <Textarea className="mt-2" placeholder={t('Reason')} value={note} onChange={(e) => setNote(e.target.value)} />}
              {act === 'settle' && mode === 'payroll' && <p className="mt-2 text-xs text-muted">{t('The employee must agree in writing when one salary repays more than 10% of the wage; the half-wage limit (Art. 93) still applies.')}</p>}
              <div className="mt-3 flex gap-2">
                <Button loading={m.isPending} onClick={() => m.mutate()}>{t('Confirm')}</Button>
                <Button variant="secondary" onClick={() => setAct(null)}>{t('Back')}</Button>
              </div>
              {m.error && <div className="mt-2"><ErrorBox error={m.error} /></div>}
            </div>
          )}
        </div>
      )}
    </Modal>
  )
}

export default function Loans() {
  const { t, lang } = useI18n()
  const qc = useQueryClient()
  const [status, setStatus] = useState('')
  const q = useQuery({ queryKey: ['loans', status], queryFn: () => api.loans(status ? { status } : {}) })
  const [open, setOpen] = useState<string | null>(null)
  const [add, setAdd] = useState(false)
  const post = useMutation({ mutationFn: () => api.postDueInstallments(monthStart(todayISO())), onSuccess: () => qc.invalidateQueries({ queryKey: ['loans'] }) })
  return (
    <div className="flex flex-col gap-5">
      <PageHeader title={t('Loans & advances')} subtitle={t('Pay out by cash or bank transfer, recover from payroll within the Saudi Labor Law limits')}
        actions={<div className="flex gap-2">
          <Button variant="secondary" loading={post.isPending} onClick={() => post.mutate()}>{t("Add this month's installments to payroll")}</Button>
          <Button onClick={() => setAdd(true)}><Plus className="size-4" />{t('New loan or advance')}</Button></div>} />
      {post.data && <p className="text-sm text-emerald-700">{post.data.posted.length} {t('installment(s) added to payroll')}</p>}
      {post.error && <ErrorBox error={post.error} />}
      {q.isLoading ? <Spinner /> : q.error ? <ErrorBox error={q.error} /> : (
        <>
          <div className="grid grid-cols-1 gap-3 sm:grid-cols-3">
            <Stat label={t('Outstanding')} value={fmtMoney(q.data.summary.outstanding, lang)} tone="amber" />
            <Stat label={t('Being repaid')} value={q.data.summary.repaying} />
            <Stat label={t('Approved, to pay out')} value={q.data.summary.to_pay} tone="blue" />
          </div>
          <Card action={<Select className="w-44" value={status} onChange={(e) => setStatus(e.target.value)}>
            <option value="">{t('All')}</option>{['Approved', 'Disbursed', 'Repaying', 'Settled', 'Cancelled'].map((s) => <option key={s} value={s}>{t(s)}</option>)}</Select>}>
            {!q.data.rows.length ? <Empty title={t('No loans or advances yet')} icon={<HandCoins />}>{t('Employees request them in Services; approved requests appear here to pay out.')}</Empty> : (
              <Table head={[t('Employee'), t('Type'), t('Amount'), t('Monthly installment'), t('Outstanding'), t('Status')]}>
                {q.data.rows.map((r: any) => (
                  <tr key={r.name}>
                    <td className="py-2"><button className="font-medium text-brand hover:underline" onClick={() => setOpen(r.name)}>{r.employee_name}</button><div className="text-xs text-muted">{r.name}</div></td>
                    <td>{t(r.loan_type)}</td><td>{fmtMoney(r.amount, lang)}</td>
                    <td>{fmtMoney(r.installment_amount, lang)} × {r.installments}</td>
                    <td className="font-semibold">{fmtMoney(r.outstanding, lang)}</td>
                    <td><StatusBadge status={r.status} /></td>
                  </tr>
                ))}
              </Table>
            )}
          </Card>
          {open && <LoanDetail name={open} accounts={q.data.accounts} onClose={() => setOpen(null)} />}
        </>
      )}
      {add && <NewLoan onClose={() => setAdd(false)} onDone={(n) => { setAdd(false); qc.invalidateQueries({ queryKey: ['loans'] }); setOpen(n) }} />}
    </div>
  )
}
