import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { CalendarPlus } from 'lucide-react'
import { useState } from 'react'
import { Badge, Button, Card, Empty, ErrorBox, Field, Input, Modal, PageHeader, Select, Spinner, StatusBadge, Textarea } from '../components/ui'
import { ApprovalChain } from '../components/ApprovalChain'
import { LeaveLedger } from '../components/LeaveLedger'
import { api, uploadFile, type LeaveTypeOption } from '../lib/api'
import { fmtDate, fmtNumber, todayISO } from '../lib/format'
import { useI18n } from '../lib/i18n'
import { FieldInput, isEmpty } from '../components/FieldInput'

function ApplyForm({ onDone, again }: { onDone: (warnings: string[]) => void; again?: any }) {
  const { t } = useI18n()
  const types = useQuery<LeaveTypeOption[]>({ queryKey: ['leaveTypes'], queryFn: api.leaveTypes })
  const today = todayISO()
  const [form, setForm] = useState({ leave_type: again?.leave_type ?? '', from_date: again?.from_date ?? today, to_date: again?.to_date ?? today,
    half_day: !!Number(again?.half_day), reason: again?.description ?? '', event_date: '', relation: '' })
  const [file, setFile] = useState<File | null>(null)
  const extraSpec = useQuery({ queryKey: ['leaveForm'], queryFn: api.leaveForm, staleTime: 300_000 })
  const [extra, setExtra] = useState<Record<string, any>>({})
  const [extraFiles, setExtraFiles] = useState<Record<string, File>>({})
  const extraMissing = (extraSpec.data?.fields ?? []).filter((f: any) =>
    (f.fieldtype === 'Attach' || f.fieldtype === 'Attach Image') ? !extraFiles[f.fieldname] : isEmpty(extra[f.fieldname]))
  const rule = types.data?.find((x) => x.leave_type === form.leave_type)?.rule ?? null
  const qc = useQueryClient()
  const m = useMutation({
    mutationFn: async () => {
      const values: Record<string, any> = { ...extra }
      for (const [k, f] of Object.entries(extraFiles)) values[k] = (await uploadFile('', '', f))?.file_url
      const r: any = await api.applyLeave({
        extra: values,
        leave_type: form.leave_type, from_date: form.from_date, to_date: form.to_date, reason: form.reason,
        half_day: form.half_day ? 1 : 0, half_day_date: form.half_day ? form.from_date : undefined,
        event_date: rule?.requires_event_date ? form.event_date || undefined : undefined,
        relation: rule?.relations.length ? form.relation || undefined : undefined,
        previous: again?.name,
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
  const days = useQuery({
    queryKey: ['leaveDays', form.leave_type, form.from_date, form.to_date, form.half_day],
    queryFn: () => api.leaveDays({ leave_type: form.leave_type, from_date: form.from_date, to_date: form.to_date, half_day: form.half_day ? 1 : 0 }),
    enabled: !!form.leave_type && !!form.from_date && !!form.to_date && form.to_date >= form.from_date,
    retry: false,
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
      {days.data && days.data.days != null && (
        <div className="rounded-xl border border-line bg-surface p-3 text-sm" data-testid="leave-days">
          <div className="font-medium">{t('Days counted')}: {fmtNumber(days.data.days)}</div>
          {days.data.text && <div className="text-xs text-muted">{days.data.text}</div>}
          {days.data.must_start_working_day && <div className="text-xs text-red-700">{t('This leave must start and end on a working day.')}</div>}
          {days.data.min_notice_days ? <div className="text-xs text-muted">{t('Request at least')} {days.data.min_notice_days} {t('day(s) in advance')}</div> : null}
        </div>
      )}
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
      {(extraSpec.data?.fields ?? []).map((f: any) => (
        <Field key={f.fieldname} label={`${f.label} *`} hint={f.description ?? undefined}>
          {f.fieldtype === 'Attach' || f.fieldtype === 'Attach Image'
            ? <Input type="file" accept=".pdf,image/*" className="py-1.5" onChange={(e) => { const x = e.target.files?.[0]; setExtraFiles((s) => { const n = { ...s }; if (x) n[f.fieldname] = x; else delete n[f.fieldname]; return n }) }} />
            : <FieldInput spec={f} value={extra[f.fieldname]} lookupSource="ess" onChange={(v) => { if (m.error) m.reset(); setExtra((s) => ({ ...s, [f.fieldname]: v })) }} />}
        </Field>
      ))}
      {!!extraSpec.data?.auto?.length && (
        <p className="text-xs text-muted">{t('Filled automatically')}: {extraSpec.data.auto.map((a) => `${a.label} (${t('next working day after the leave')})`).join(', ')}</p>
      )}
      {m.error && <ErrorBox error={m.error} />}
      <Button type="submit" loading={m.isPending} disabled={extraMissing.length > 0}>{t('Submit request')}</Button>
    </form>
  )
}

export default function MyLeave() {
  const { t, lang } = useI18n()
  const balances = useQuery<any>({ queryKey: ['balances'], queryFn: api.balances })
  const leaves = useQuery<any[]>({ queryKey: ['myLeaves'], queryFn: api.myLeaves })
  const [open, setOpen] = useState(false)
  const [again, setAgain] = useState<any>(null)
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
      <details className="group mb-5 rounded-2xl border border-line bg-white p-4 shadow-sm sm:p-5">
        <summary className="cursor-pointer list-none font-semibold text-ink"><span className="me-2 inline-block transition group-open:rotate-90 rtl:group-open:-rotate-90">›</span>{t('Leave ledger & sick-leave year')}</summary>
        <div className="mt-4"><LeaveLedger /></div>
      </details>
      <Card title={t('My requests')}>
        {leaves.isLoading ? <Spinner /> : !leaves.data?.length ? <Empty title={t('All caught up')} /> : (
          <ul className="divide-y divide-line">
            {leaves.data.map((l) => (
              <li key={l.name} className="flex flex-wrap items-center justify-between gap-3 py-3">
                <div>
                  <div className="font-medium">{l.leave_type} <span className="text-sm font-normal text-muted">· {fmtNumber(l.total_leave_days, lang, 1)} {t('days')}</span></div>
                  <div className="text-sm text-muted">{fmtDate(l.from_date, lang)} → {fmtDate(l.to_date, lang)}</div>
                  {l.status === 'Rejected' && l.rejection_note && <div className="mt-1 rounded-lg bg-red-50 px-2 py-1 text-xs text-red-800">{t('Reason')}: {l.rejection_note}</div>}
                  {l.status === 'Open' && <div className="mt-1"><ApprovalChain doctype="Leave Application" name={l.name} /></div>}
                </div>
                <div className="flex items-center gap-2">
                  {l.workflow_state && l.workflow_state !== l.status && <Badge tone="blue">{l.workflow_state}</Badge>}
                  <StatusBadge status={l.status} />
                  {l.status === 'Rejected' && (
                    <Button size="sm" variant="secondary" onClick={() => { setAgain(l); setOpen(true) }}>{t('Apply again')}</Button>
                  )}
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
      <Modal open={open} onClose={() => { setOpen(false); setAgain(null) }} title={again ? t('Apply again') : t('Apply for leave')}>
        <ApplyForm key={again?.name ?? 'new'} again={again} onDone={(w) => { setOpen(false); setAgain(null); setNotice(w) }} />
      </Modal>
    </div>
  )
}
