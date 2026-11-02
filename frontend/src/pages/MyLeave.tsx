import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { CalendarPlus } from 'lucide-react'
import { useState } from 'react'
import { Badge, Button, Card, Empty, ErrorBox, Field, Input, Modal, PageHeader, Select, Spinner, StatusBadge, Textarea } from '../components/ui'
import { api, uploadFile, type LeaveTypeOption } from '../lib/api'
import { fmtDate, fmtNumber, todayISO } from '../lib/format'
import { useI18n } from '../lib/i18n'

function ApplyForm({ onDone }: { onDone: (warnings: string[]) => void }) {
  const { t } = useI18n()
  const types = useQuery<LeaveTypeOption[]>({ queryKey: ['leaveTypes'], queryFn: api.leaveTypes })
  const today = todayISO()
  const [form, setForm] = useState({ leave_type: '', from_date: today, to_date: today, half_day: false, reason: '', event_date: '', relation: '' })
  const [file, setFile] = useState<File | null>(null)
  const rule = types.data?.find((x) => x.leave_type === form.leave_type)?.rule ?? null
  const qc = useQueryClient()
  const m = useMutation({
    mutationFn: async () => {
      const r: any = await api.applyLeave({
        leave_type: form.leave_type, from_date: form.from_date, to_date: form.to_date, reason: form.reason,
        half_day: form.half_day ? 1 : 0, half_day_date: form.half_day ? form.from_date : undefined,
        event_date: rule?.requires_event_date ? form.event_date || undefined : undefined,
        relation: rule?.relations.length ? form.relation || undefined : undefined,
      })
      if (file) await uploadFile('Leave Application', r.name, file)
      return r
    },
    onSuccess: (r: any) => {
      qc.invalidateQueries({ queryKey: ['myLeaves'] })
      qc.invalidateQueries({ queryKey: ['balances'] })
      onDone(r.warnings ?? [])
    },
  })
  const set = (k: string, v: unknown) => {
    if (m.error) m.reset() // a stale error must not linger once the user edits the request
    setForm((f) => ({ ...f, [k]: v }))
  }
  return (
    <form className="flex flex-col gap-4" onSubmit={(e) => { e.preventDefault(); m.mutate() }}>
      <Field label={t('Leave type')}>
        <Select required value={form.leave_type} onChange={(e) => set('leave_type', e.target.value)}>
          <option value="">—</option>
          {(types.data ?? []).map((lt) => <option key={lt.leave_type} value={lt.leave_type}>{lt.leave_type}</option>)}
        </Select>
      </Field>
      {rule && (
        <div className="rounded-xl bg-brand-50 p-3 text-sm text-brand-700">
          {t('Saudi Labor Law rule')}: {rule.max_days ? `${t('up to')} ${rule.max_days} ${t('days')}` : t('no fixed limit')}
          {rule.lifetime_limit ? ` · ${rule.lifetime_limit}× ${t('per employment')}` : ''}
          {rule.requires_attachment ? ` · ${t('a supporting document is needed before approval')}` : ''}
        </div>
      )}
      <div className="grid grid-cols-2 gap-3">
        <Field label={t('From')}><Input type="date" required value={form.from_date} onChange={(e) => { set('from_date', e.target.value); if (e.target.value > form.to_date) set('to_date', e.target.value) }} /></Field>
        <Field label={t('To')}><Input type="date" required min={form.from_date} value={form.to_date} onChange={(e) => set('to_date', e.target.value)} /></Field>
      </div>
      {rule?.requires_event_date && (
        <Field label={rule.event_label ? t(rule.event_label) : t('Event date')}><Input type="date" required value={form.event_date} onChange={(e) => set('event_date', e.target.value)} /></Field>
      )}
      {!!rule?.relations.length && (
        <Field label={t('Relation')}>
          <Select required value={form.relation} onChange={(e) => set('relation', e.target.value)}>
            <option value="">—</option>
            {rule.relations.map((r) => <option key={r} value={r}>{t(r)}</option>)}
          </Select>
        </Field>
      )}
      {!rule?.requires_event_date && (
        <label className="flex items-center gap-2 text-sm"><input type="checkbox" checked={form.half_day} onChange={(e) => set('half_day', e.target.checked)} className="size-4 accent-[var(--color-brand)]" /> {t('Half day')}</label>
      )}
      <Field label={t('Reason')}><Textarea value={form.reason} maxLength={1000} onChange={(e) => set('reason', e.target.value)} /></Field>
      <Field label={t('Supporting document') + (rule?.requires_attachment ? ' *' : '')} hint={t('Medical certificate, birth certificate or other proof (PDF or image).')}>
        <Input type="file" accept=".pdf,image/*" onChange={(e) => setFile(e.target.files?.[0] ?? null)} className="py-1.5" />
      </Field>
      {m.error && <ErrorBox error={m.error} />}
      <Button type="submit" loading={m.isPending}>{t('Submit request')}</Button>
    </form>
  )
}

export default function MyLeave() {
  const { t, lang } = useI18n()
  const balances = useQuery<any>({ queryKey: ['balances'], queryFn: api.balances })
  const leaves = useQuery<any[]>({ queryKey: ['myLeaves'], queryFn: api.myLeaves })
  const [open, setOpen] = useState(false)
  const [notice, setNotice] = useState<string[] | null>(null)
  const qc = useQueryClient()
  const withdraw = useMutation({ mutationFn: api.withdrawLeave, onSuccess: () => { qc.invalidateQueries({ queryKey: ['myLeaves'] }); qc.invalidateQueries({ queryKey: ['balances'] }) } })
  return (
    <div>
      <PageHeader title={t('My Leave')} actions={<Button onClick={() => setOpen(true)}><CalendarPlus className="size-4" />{t('Apply for leave')}</Button>} />
      {notice && (
        <div className="mb-4 rounded-xl border border-emerald-200 bg-emerald-50 p-3 text-sm text-emerald-800">
          <p className="font-medium">{t('Request submitted')}</p>
          {notice.map((w) => <p key={w} className="mt-1 text-amber-800">{w}</p>)}
        </div>
      )}
      {balances.isLoading ? <Spinner /> : balances.error ? <ErrorBox error={balances.error} /> : (
        <div className="mb-5 grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
          {balances.data.balances.map((b: any) => {
            const pct = b.allocated ? Math.max(0, Math.min(100, (100 * b.balance) / b.allocated)) : 0
            return (
              <div key={b.leave_type} className="rounded-2xl border border-line bg-white p-4 shadow-sm">
                <div className="text-sm text-muted">{b.leave_type}</div>
                <div className="mt-1 text-3xl font-semibold tabular-nums">{fmtNumber(b.balance, lang, 1)} <span className="text-sm font-normal text-muted">{t('days')}</span></div>
                <div className="mt-3 h-2 rounded-full bg-surface"><div className="h-2 rounded-full bg-brand" style={{ width: `${pct}%` }} /></div>
                <div className="mt-2 flex justify-between text-xs text-muted">
                  <span>{t('Allocated')} {fmtNumber(b.allocated, lang, 1)}</span>
                  <span>{t('Taken')} {fmtNumber(b.taken, lang, 1)}</span>
                  {b.pending > 0 && <span>{t('Pending')} {fmtNumber(b.pending, lang, 1)}</span>}
                </div>
              </div>
            )
          })}
        </div>
      )}
      <Card title={t('My requests')}>
        {leaves.isLoading ? <Spinner /> : !leaves.data?.length ? <Empty title={t('All caught up')} /> : (
          <ul className="divide-y divide-line">
            {leaves.data.map((l) => (
              <li key={l.name} className="flex flex-wrap items-center justify-between gap-3 py-3">
                <div>
                  <div className="font-medium">{l.leave_type} <span className="text-sm font-normal text-muted">· {fmtNumber(l.total_leave_days, lang, 1)} {t('days')}</span></div>
                  <div className="text-sm text-muted">{fmtDate(l.from_date, lang)} → {fmtDate(l.to_date, lang)}</div>
                </div>
                <div className="flex items-center gap-2">
                  {l.workflow_state && l.workflow_state !== l.status && <Badge tone="blue">{l.workflow_state}</Badge>}
                  <StatusBadge status={l.status} />
                  {l.docstatus === 0 && l.status === 'Open' && (
                    <Button size="sm" variant="ghost" loading={withdraw.isPending && withdraw.variables === l.name} onClick={() => withdraw.mutate(l.name)}>{t('Withdraw')}</Button>
                  )}
                </div>
              </li>
            ))}
          </ul>
        )}
        {withdraw.error && <div className="mt-3"><ErrorBox error={withdraw.error} /></div>}
      </Card>
      <Modal open={open} onClose={() => setOpen(false)} title={t('Apply for leave')}>
        <ApplyForm onDone={(w) => { setOpen(false); setNotice(w) }} />
      </Modal>
    </div>
  )
}
