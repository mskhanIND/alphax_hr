import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Plus, Receipt } from 'lucide-react'
import { useState } from 'react'
import { Button, Card, Empty, ErrorBox, Field, Input, Modal, PageHeader, Select, Spinner, StatusBadge, Textarea } from '../components/ui'
import { api, uploadFile } from '../lib/api'
import { fmtDate, fmtMoney, todayISO } from '../lib/format'
import { useI18n } from '../lib/i18n'

export default function MyExpenses() {
  const { t, lang } = useI18n()
  const qc = useQueryClient()
  const q = useQuery<any[]>({ queryKey: ['expenses'], queryFn: api.expenses })
  const types = useQuery({ queryKey: ['expense-types'], queryFn: api.expenseTypes })
  const [open, setOpen] = useState(false)
  const [f, setF] = useState<any>({ expense_date: todayISO() })
  const [file, setFile] = useState<File | null>(null)
  const m = useMutation({
    mutationFn: async () => { const r = await api.submitExpense(f); if (file) await uploadFile('Expense Claim', r.name, file); return r },
    onSuccess: () => { setOpen(false); setF({ expense_date: todayISO() }); setFile(null); qc.invalidateQueries({ queryKey: ['expenses'] }) },
  })
  const w = useMutation({ mutationFn: api.withdrawExpense, onSuccess: () => qc.invalidateQueries({ queryKey: ['expenses'] }) })
  return (
    <div>
      <PageHeader title={t('My expenses')} subtitle={t('Claim business expenses with the receipt')}
        actions={<Button onClick={() => setOpen(true)}><Plus className="size-4" />{t('New claim')}</Button>} />
      <Card>
        {q.isLoading ? <Spinner /> : q.error ? <ErrorBox error={q.error} /> : !q.data?.length ? <Empty title={t('No expense claims')} icon={<Receipt />} /> : (
          <ul className="divide-y divide-line">
            {q.data.map((r) => (
              <li key={r.name} className="flex flex-wrap items-center gap-3 py-3">
                <div className="min-w-0 flex-1">
                  <div className="font-medium">{fmtMoney(r.total_claimed_amount, lang)}</div>
                  <div className="text-sm text-muted">{r.name} · {fmtDate(r.posting_date, lang)}{r.total_sanctioned_amount && r.docstatus === 1 ? ` · ${t('Approved')}: ${fmtMoney(r.total_sanctioned_amount, lang)}` : ''}</div>
                </div>
                <StatusBadge status={r.approval_status === 'Draft' ? 'Pending' : r.approval_status} />
                {r.docstatus === 0 && r.approval_status === 'Draft' && <Button size="sm" variant="secondary" loading={w.isPending && w.variables === r.name} onClick={() => w.mutate(r.name)}>{t('Withdraw')}</Button>}
              </li>
            ))}
          </ul>
        )}
        {w.error && <ErrorBox error={w.error} />}
      </Card>
      <Modal open={open} onClose={() => setOpen(false)} title={t('New claim')}
        footer={<><Button variant="secondary" onClick={() => setOpen(false)}>{t('Cancel')}</Button>
          <Button disabled={!f.expense_type || !(Number(f.amount) > 0)} loading={m.isPending} onClick={() => m.mutate()}>{t('Submit claim')}</Button></>}>
        <div className="grid gap-4">
          <Field label={t('Expense type')}>
            <Select value={f.expense_type ?? ''} onChange={(e) => setF({ ...f, expense_type: e.target.value })}>
              <option value="">—</option>{(types.data ?? []).map((x: any) => <option key={x.name} value={x.name}>{x.name}</option>)}
            </Select>
          </Field>
          <div className="grid grid-cols-2 gap-3">
            <Field label={t('Amount')}><Input type="number" min="0" step="0.01" inputMode="decimal" value={f.amount ?? ''} onChange={(e) => setF({ ...f, amount: e.target.value })} /></Field>
            <Field label={t('Date')}><Input type="date" value={f.expense_date} max={todayISO()} onChange={(e) => setF({ ...f, expense_date: e.target.value })} /></Field>
          </div>
          <Field label={t('Description')}><Textarea value={f.description ?? ''} onChange={(e) => setF({ ...f, description: e.target.value })} /></Field>
          <Field label={t('Receipt')}><input type="file" accept="image/*,application/pdf" capture="environment" onChange={(e) => setFile(e.target.files?.[0] ?? null)} className="text-sm" /></Field>
          {m.error && <ErrorBox error={m.error} />}
        </div>
      </Modal>
    </div>
  )
}
